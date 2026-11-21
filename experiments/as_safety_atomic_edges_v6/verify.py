"""Independently replay two answer-given E→B format-oracle responses."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
import subprocess
from pathlib import Path

from experiments.as_safety_atomic_edges_v1 import run as v1_run
from experiments.as_safety_atomic_edges_v1 import verify as v1_verify
from experiments.as_safety_atomic_edges_v1.event_owner import (
    event_owner_messages,
    event_owner_schema,
)
from experiments.as_safety_atomic_edges_v4 import verify as v4_verify
from experiments.as_safety_atomic_edges_v5 import verify as v5_verify

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout/as-safety-eb-controls-v5-cases.json"
METHOD = ROOT / "docs/portfolio/nlu_safety_atomic_edge_format_oracle_v6_method.md"
REFERENCE_PROTOCOL = (
    ROOT / "evals/structured_nlu/data/ai_heldout/as-safety-eb-controls-v5-development-protocol.json"
)
REFERENCE_JOURNAL = (
    ROOT
    / "evals/structured_nlu/data/ai_heldout/as-safety-eb-controls-v5-development-journal.v1.jsonl"
)
REFERENCE_PROTOCOL_SHA = "9c2733c2faf66051519442e2c6590c3854234481f81330e8fe939606cd1ae95e"
REFERENCE_JOURNAL_SHA = "949b528284b04ee8fbccb9053f4ad428d33b3aaa190d9954d0ab1ecc5cc4dab8"
INPUTS = {
    "method_v6": METHOD,
    "reviewed_v5_cases": DATA,
    "reference_v5_protocol": REFERENCE_PROTOCOL,
    "reference_v5_journal": REFERENCE_JOURNAL,
}
SOURCE_PATHS = v5_verify.SOURCE_PATHS | {
    "experiments/as_safety_atomic_edges_v6/__init__.py",
    "experiments/as_safety_atomic_edges_v6/run.py",
    "experiments/as_safety_atomic_edges_v6/verify.py",
    "tests/test_as_safety_atomic_edge_format_oracle_v6.py",
}
POST_RUN_REPLAY_SOURCES = {
    "experiments/as_safety_atomic_edges_v6/run.py",
    "experiments/as_safety_atomic_edges_v6/verify.py",
    "tests/test_as_safety_atomic_edge_format_oracle_v6.py",
}
ORDER = ("F1", "F2")
JOURNAL = (
    ROOT
    / "evals/structured_nlu/data/ai_heldout/as-safety-eb-format-oracle-v6-development-journal.v1.jsonl"
)
PRIVATE_DIR = Path("/private/tmp/as-safety-eb-format-oracle-v6-raw")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
ROW_FIELDS = {
    "event",
    "arm",
    "request_sha256",
    "finish_reason",
    "error_code",
    "http_status",
    "raw_sha256",
    "raw_bytes",
    "request_latency_ms",
}


class VerificationError(ValueError):
    """A bounded failure that does not reveal private prompts or responses."""


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


LOADED_VERIFIER_SHA256 = _digest_file(Path(__file__))


def _check_loaded_verifier() -> None:
    if _digest_file(Path(__file__)) != LOADED_VERIFIER_SHA256:
        raise VerificationError("verifier source changed during replay")


def _frozen(commit: str, relative: str) -> bytes:
    if (
        type(commit) is not str
        or not COMMIT_RE.fullmatch(commit)
        or relative.startswith("/")
        or ".." in Path(relative).parts
    ):
        raise VerificationError("frozen reference invalid")
    return subprocess.run(
        ("git", "show", f"{commit}:{relative}"),
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


def _json(raw: bytes) -> dict:
    try:
        parsed = v1_verify._json(raw.decode("utf-8"))
    except (UnicodeDecodeError, v1_verify.VerificationError) as error:
        raise VerificationError("JSON invalid") from error
    if type(parsed) is not dict:
        raise VerificationError("JSON object required")
    return parsed


def _case(raw: bytes) -> dict:
    try:
        return v5_verify._source_cases(raw)["PC01"]
    except (v5_verify.VerificationError, KeyError) as error:
        raise VerificationError("reviewed PC01 differs") from error


def _request_sha(case: dict, arm: str, protocol: dict) -> str:
    """Rebuild the wire request without importing v6's candidate runner."""
    if arm not in ORDER:
        raise VerificationError("oracle arm differs")
    messages = event_owner_messages(
        case["user_message"],
        case["event_span"],
        case["occurrence"],
        product_index=case["product_index"],
        target_mention=case["target_mention"],
    )
    user = messages[1]["content"]
    changes = (
        ("event_subject_evidence_span에는 E와 B를 연결하는 연속 원문 구절을 인용하세요. ", ""),
        ("implicit이면 앞선 문장의 연결 근거를 인용할 수 있습니다. ", ""),
        (
            "주체를 확인할 수 없으면 unresolved와 두 구절 모두 null을 반환하세요. ",
            "주체를 확인할 수 없으면 unresolved와 subject_span=null을 반환하세요. ",
        ),
        (
            "각 구절은 clause_index와 quote를 가진 객체 또는 null입니다. ",
            "subject_span은 clause_index와 quote를 가진 객체 또는 null입니다. ",
        ),
        (
            "JSON 객체 하나에 subject_span, event_subject_kind, "
            "event_subject_evidence_span 세 키만 반환하세요.",
            "JSON 객체 하나에 subject_span, event_subject_kind 두 키만 반환하세요.",
        ),
    )
    for old, new in changes:
        if user.count(old) != 1:
            raise VerificationError("frozen source prompt differs")
        user = user.replace(old, new)
    gold = {
        "subject_span": case["gold_subject_span"],
        "event_subject_kind": case["gold_kind"],
    }
    if arm == "F1":
        answer = json.dumps(gold, ensure_ascii=False, separators=(",", ":"))
        cue = f"\n형식 오라클 F1: 정답 JSON 객체는 {answer} 입니다. 두 필드의 값과 구조를 바꾸지 말고 이 객체를 반환하세요."
    else:
        span = gold["subject_span"]
        cue = (
            f"\n형식 오라클 F2: 위험의 물리적 출처 B는 {span['clause_index']}번 문장의 "
            f"{span['quote']}이고 연결 종류는 {gold['event_subject_kind']}입니다. "
            "이 문장 번호, 구절, 종류를 두 필드 JSON 객체에 담아 반환하세요."
        )
    messages[1] = {"role": "user", "content": user + cue}
    schema = event_owner_schema(case["user_message"])
    del schema["properties"]["event_subject_evidence_span"]
    schema["required"].remove("event_subject_evidence_span")
    policy = protocol["request_policy"]
    payload = {
        "model": protocol["model_id"],
        "messages": messages,
        "max_tokens": policy["max_tokens"],
        "temperature": policy["temperature"],
        "repeat_penalty": policy["repeat_penalty"],
        "stop": policy["stop"],
        "seed": policy["seed"],
        "response_format": {"type": "json_object", "schema": schema},
    }
    return _digest(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"))


def _identity() -> dict:
    return {
        "kind": "as_safety_eb_format_oracle_v6_development_v1",
        "claim_scope": "answer_given_format_oracle_only_no_extraction_accuracy",
        "case_id": "PC01",
        "call_order": list(ORDER),
        "response_format": "v4_subject_only_two_field_schema_constrained_json",
        "oracle_labels_in_both_requests": True,
        "reference_v5_protocol_sha256": REFERENCE_PROTOCOL_SHA,
        "reference_v5_journal_sha256": REFERENCE_JOURNAL_SHA,
        "model_sha256": v1_run.MODEL_SHA,
        "server_image_digest": v1_run.IMAGE,
        "container_name": "as-safety-eb-format-oracle-v6",
        "endpoint": v1_run.ENDPOINT,
        "model_id": v1_run.MODEL_ID,
        "server_args": list(v1_run.SERVER_ARGS),
        "local_runtime": v1_run.RUNTIME,
        "request_policy": v1_run.REQUEST_POLICY,
        "retry_policy": v1_run.RETRY_POLICY,
        "private_output": v1_run.PRIVATE_OUTPUT,
        "score_scope": "format_oracle_only; no extraction_accuracy; no B_to_A; no safety_route",
        "token_usage": "not_collected_by_completion_transport",
    }


def check_protocol(path: Path, model_path: Path) -> tuple[dict, str, dict]:
    _check_loaded_verifier()
    raw = path.read_bytes()
    protocol = _json(raw)
    expected = _identity()
    if set(protocol) != set(expected) | {
        "frozen_code_commit",
        "source_manifest",
        "input_hashes",
        "request_sha256_by_call",
    } or any(protocol.get(key) != value for key, value in expected.items()):
        raise VerificationError("protocol identity differs")
    if not model_path.is_file() or _digest_file(model_path) != v1_run.MODEL_SHA:
        raise VerificationError("model file digest differs")
    commit = protocol["frozen_code_commit"]
    if type(commit) is not str or not COMMIT_RE.fullmatch(commit):
        raise VerificationError("frozen commit differs")
    verified_inputs: dict[str, bytes] = {}
    for key, paths in (("source_manifest", SOURCE_PATHS), ("input_hashes", INPUTS)):
        manifest = protocol[key]
        if type(manifest) is not dict or set(manifest) != set(paths):
            raise VerificationError(f"{key} differs")
        for name, expected_sha in manifest.items():
            path_for_key = paths[name] if isinstance(paths, dict) else ROOT / name
            relative = path_for_key.relative_to(ROOT).as_posix()
            frozen = _frozen(commit, relative)
            if (
                type(expected_sha) is not str
                or not SHA_RE.fullmatch(expected_sha)
                or _digest(frozen) != expected_sha
            ):
                raise VerificationError(f"{key} differs")
            current = path_for_key.read_bytes()
            if key == "input_hashes":
                if current != frozen:
                    raise VerificationError(f"input differs: {name}")
                verified_inputs[name] = current
            elif name not in POST_RUN_REPLAY_SOURCES and current != frozen:
                raise VerificationError(f"source differs: {name}")
    if (
        _digest(verified_inputs["reference_v5_protocol"]) != REFERENCE_PROTOCOL_SHA
        or _digest(verified_inputs["reference_v5_journal"]) != REFERENCE_JOURNAL_SHA
    ):
        raise VerificationError("v5 reference digest differs")
    case = _case(verified_inputs["reviewed_v5_cases"])
    hashes = protocol["request_sha256_by_call"]
    if type(hashes) is not dict or set(hashes) != set(ORDER):
        raise VerificationError("request manifest differs")
    for arm in ORDER:
        if hashes[arm] != _request_sha(case, arm, protocol):
            raise VerificationError("frozen request differs")
    relative = path.resolve().relative_to(ROOT).as_posix()
    if (
        _frozen(
            subprocess.run(("git", "rev-parse", "HEAD"), cwd=ROOT, check=True, capture_output=True)
            .stdout.decode()
            .strip(),
            relative,
        )
        != raw
    ):
        raise VerificationError("protocol is not committed")
    _check_loaded_verifier()
    return protocol, _digest(raw), case


def _journal(raw: bytes, protocol_sha: str, protocol: dict, case: dict) -> list[dict]:
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise VerificationError("journal encoding differs") from error
    if len(lines) != 3:
        raise VerificationError("journal row count differs")
    rows = [_json(line.encode("utf-8")) for line in lines]
    if rows[0] != {"event": "header", "protocol_sha256": protocol_sha}:
        raise VerificationError("journal header differs")
    for row, arm in zip(rows[1:], ORDER, strict=True):
        if (
            set(row) != ROW_FIELDS
            or row["event"] != "result"
            or row["arm"] != arm
            or row["request_sha256"] != protocol["request_sha256_by_call"][arm]
            or row["request_sha256"] != _request_sha(case, arm, protocol)
        ):
            raise VerificationError("journal request identity differs")
        latency = row["request_latency_ms"]
        if type(latency) not in {int, float} or not math.isfinite(latency) or latency < 0:
            raise VerificationError("journal latency invalid")
        finish, error, status = row["finish_reason"], row["error_code"], row["http_status"]
        has_raw = row["raw_sha256"] is not None and row["raw_bytes"] is not None
        if finish == "stop":
            valid = error is None and status is None and has_raw
        elif finish == "length":
            valid = error == "finish_length" and status is None and has_raw
        elif finish is None:
            valid = (
                type(error) is str
                and error in v5_verify.TRANSPORT_CODES
                and row["raw_sha256"] is None
                and row["raw_bytes"] is None
                and (
                    type(status) is int and 100 <= status <= 599
                    if error in {"http_status", "http_error"}
                    else status is None
                )
            )
        else:
            valid = False
        if not valid:
            raise VerificationError("journal response metadata differs")
        if has_raw and (
            type(row["raw_sha256"]) is not str
            or not SHA_RE.fullmatch(row["raw_sha256"])
            or type(row["raw_bytes"]) is not int
            or row["raw_bytes"] <= 0
        ):
            raise VerificationError("journal raw metadata invalid")
    return rows[1:]


def _raw(private_dir: Path, row: dict) -> str | None:
    if row["raw_sha256"] is None:
        return None
    path = private_dir / f"{row['arm']}.json.txt"
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise VerificationError("private response file or mode differs")
    content = path.read_bytes()
    if _digest(content) != row["raw_sha256"] or len(content) != row["raw_bytes"]:
        raise VerificationError("private response digest differs")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise VerificationError("private response encoding differs") from error


def verify_result(
    protocol_path: Path, model_path: Path, journal_path: Path, private_dir: Path
) -> dict:
    if journal_path.absolute() != JOURNAL or private_dir.absolute() != PRIVATE_DIR:
        raise VerificationError("one-shot output paths differ")
    protocol, protocol_sha, case = check_protocol(protocol_path, model_path)
    if (
        private_dir.is_symlink()
        or not private_dir.is_dir()
        or private_dir.resolve().is_relative_to(ROOT)
        or stat.S_IMODE(private_dir.stat().st_mode) != 0o700
    ):
        raise VerificationError("private directory or mode differs")
    journal_bytes = journal_path.read_bytes()
    rows = _journal(journal_bytes, protocol_sha, protocol, case)
    expected_files = {f"{row['arm']}.json.txt" for row in rows if row["raw_sha256"] is not None}
    if {entry.name for entry in private_dir.iterdir()} != expected_files:
        raise VerificationError("unexpected private response file")
    metrics = {
        "calls": 2,
        "contract_pass": 0,
        "contract_errors": 0,
        "transport_or_length_errors": 0,
        "valid_nonnull": 0,
        "source_quote_anchored": 0,
        "given_B_exact": 0,
        "given_kind_exact": 0,
        "full_object_match": 0,
        "valid_null": 0,
        "request_latency_ms_sum": round(sum(row["request_latency_ms"] for row in rows), 3),
    }
    per_arm = []
    for row in rows:
        raw = _raw(private_dir, row)
        decision = None
        contract_error_code = None
        if row["error_code"] is not None or row["finish_reason"] != "stop":
            metrics["transport_or_length_errors"] += 1
        elif raw is not None:
            try:
                decision = v4_verify.replay_subject_only(
                    raw, case["user_message"], case["event_span"]
                )
            except v1_verify.VerificationError as error:
                metrics["contract_errors"] += 1
                contract_error_code = v5_verify.CONTRACT_ERRORS.get(str(error), "contract_invalid")
            else:
                metrics["contract_pass"] += 1
        valid_nonnull = decision is not None and decision["subject_span"] is not None
        B_exact = bool(
            valid_nonnull
            and v5_verify._same_quote(decision["subject_span"], case["gold_subject_span"])
        )
        kind_exact = decision is not None and decision["event_subject_kind"] == case["gold_kind"]
        full_match = B_exact and kind_exact
        if decision is not None:
            metrics["valid_nonnull"] += int(valid_nonnull)
            metrics["source_quote_anchored"] += int(valid_nonnull)
            metrics["given_B_exact"] += int(B_exact)
            metrics["given_kind_exact"] += int(kind_exact)
            metrics["full_object_match"] += int(full_match)
            metrics["valid_null"] += int(decision["subject_span"] is None)
        per_arm.append(
            {
                "arm": row["arm"],
                "contract_pass": decision is not None,
                "contract_error_code": contract_error_code,
                "valid_nonnull": bool(valid_nonnull) if decision is not None else None,
                "source_quote_anchored": bool(valid_nonnull) if decision is not None else None,
                "given_B_exact": B_exact if decision is not None else None,
                "given_kind_exact": bool(kind_exact) if decision is not None else None,
                "full_object_match": bool(full_match) if decision is not None else None,
                "valid_null": decision["subject_span"] is None if decision is not None else None,
                "request_latency_ms": row["request_latency_ms"],
            }
        )
    _check_loaded_verifier()
    return {
        "claim_scope": protocol["claim_scope"],
        "protocol_sha256": protocol_sha,
        "journal_sha256": _digest(journal_bytes),
        "frozen_verifier_sha256": protocol["source_manifest"][
            "experiments/as_safety_atomic_edges_v6/verify.py"
        ],
        "replay_verifier_sha256": LOADED_VERIFIER_SHA256,
        "summary": metrics,
        "per_arm": per_arm,
        "gold_in_both_requests": True,
        "extraction_accuracy_evaluated": False,
        "B_to_A_evaluated": False,
        "final_safety_route_evaluated": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--private-dir", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            verify_result(args.protocol, args.model_path, args.journal, args.private_dir),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
