"""Independently replay six source-only E→B candidate-order controls."""

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
from experiments.as_safety_v2.source_lattice import generate_source_lattice

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout/as-safety-eb-controls-v5-cases.json"
METHOD = ROOT / "docs/portfolio/nlu_safety_eb_candidate_order_v7_method.md"
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
    "method_v7": METHOD,
    "reviewed_v5_cases": DATA,
    "reference_v5_protocol": REFERENCE_PROTOCOL,
    "reference_v5_journal": REFERENCE_JOURNAL,
}
SOURCE_PATHS = v5_verify.SOURCE_PATHS | {
    "experiments/as_safety_v2/source_lattice.py",
    "experiments/as_safety_atomic_edges_v7/__init__.py",
    "experiments/as_safety_atomic_edges_v7/run.py",
    "experiments/as_safety_atomic_edges_v7/verify.py",
    "tests/test_as_safety_atomic_edge_candidate_order_v7.py",
}
POST_RUN_REPLAY_SOURCES = {
    "experiments/as_safety_atomic_edges_v7/run.py",
    "experiments/as_safety_atomic_edges_v7/verify.py",
    "tests/test_as_safety_atomic_edge_candidate_order_v7.py",
}
ORDER = ("PC01-A", "PC01-B", "PC01-C", "NC01-C", "NC01-B", "NC01-A")
JOURNAL = (
    ROOT
    / "evals/structured_nlu/data/ai_heldout/as-safety-eb-candidate-order-v7-development-journal.v1.jsonl"
)
PRIVATE_DIR = Path("/private/tmp/as-safety-eb-candidate-order-v7-raw")
CANDIDATE_POLICY = {"max_window_tokens": 5, "max_candidates": 192}
TOKENIZE_PATH = "/v1/chat/completions/input_tokens"
CONTEXT_TOKENS = 4096
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
ROW_FIELDS = {
    "event",
    "call",
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


def _cases(raw: bytes) -> dict[str, dict]:
    try:
        cases = v5_verify._source_cases(raw)
    except (v5_verify.VerificationError, KeyError) as error:
        raise VerificationError("reviewed controls differ") from error
    if set(cases) != {"PC01", "NC01"}:
        raise VerificationError("reviewed control cases differ")
    return cases


def _candidate_rows(case: dict) -> tuple[list[str], object]:
    lattice = generate_source_lattice(case["user_message"], **CANDIDATE_POLICY)
    if not lattice.candidates:
        raise VerificationError("source candidate list is empty")
    if lattice.truncated:
        raise VerificationError("source candidate list was truncated")
    return [f"{c.id} | {c.clause_index}번 | {c.quote}" for c in lattice.candidates], lattice


def _candidate_manifest(cases: dict[str, dict]) -> dict[str, dict]:
    manifest = {}
    for case_id in ("PC01", "NC01"):
        rows, lattice = _candidate_rows(cases[case_id])
        manifest[case_id] = {
            "source_sha256": lattice.source_sha256,
            "candidate_count": len(rows),
            "generated_count": len(lattice.generated),
            "candidate_rows_original_sha256": _digest("\n".join(rows).encode("utf-8")),
            "candidate_rows_reversed_sha256": _digest("\n".join(reversed(rows)).encode("utf-8")),
        }
    return manifest


def _gold_candidate_availability(cases: dict[str, dict]) -> dict[str, dict]:
    """Score reviewed B only after source-only candidate construction."""
    result = {}
    for case_id in ("PC01", "NC01"):
        case = cases[case_id]
        _, lattice = _candidate_rows(case)
        gold = case["gold_subject_span"]
        match = (
            next(
                (
                    item.id
                    for item in lattice.candidates
                    if (item.clause_index, item.quote) == (gold["clause_index"], gold["quote"])
                ),
                None,
            )
            if gold is not None
            else None
        )
        result[case_id] = {
            "candidate_count": len(lattice.candidates),
            "gold_B_candidate_id": match,
            "gold_B_required": gold is not None,
        }
    return result


def _request_sha(case: dict, arm: str, protocol: dict) -> str:
    """Rebuild the wire request without importing v7's candidate runner."""
    if arm not in {"A", "B", "C"}:
        raise VerificationError("candidate arm differs")
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
    if arm in {"B", "C"}:
        rows, _ = _candidate_rows(case)
        if arm == "C":
            rows.reverse()
        cue = (
            "\n아래는 원문에서 자동 생성한 구절 후보입니다. 후보는 정답 표시가 아닙니다. "
            "실제 위험이 발생한 물리적 출처를 확인할 수 있으면 후보의 원문 구절과 문장 번호를 "
            "subject_span에 사용하세요. 출처를 확인할 수 없다면 subject_span=null, "
            "event_subject_kind=unresolved로 반환하세요. 후보 번호는 출력하지 마세요.\n"
            + "\n".join(rows)
        )
        user += cue
    messages[1] = {"role": "user", "content": user}
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
        "kind": "as_safety_eb_candidate_order_v7_development_v1",
        "claim_scope": "source_only_candidate_order_controls_two_exposed_cases",
        "case_ids": ["PC01", "NC01"],
        "call_order": list(ORDER),
        "response_format": "v4_subject_only_two_field_schema_constrained_json",
        "candidate_generation": CANDIDATE_POLICY,
        "tokenizer_endpoint": TOKENIZE_PATH,
        "context_tokens": CONTEXT_TOKENS,
        "gold_in_requests": False,
        "reference_v5_protocol_sha256": REFERENCE_PROTOCOL_SHA,
        "reference_v5_journal_sha256": REFERENCE_JOURNAL_SHA,
        "model_sha256": v1_run.MODEL_SHA,
        "server_image_digest": v1_run.IMAGE,
        "container_name": "as-safety-eb-candidate-order-v7",
        "endpoint": v1_run.ENDPOINT,
        "model_id": v1_run.MODEL_ID,
        "server_args": list(v1_run.SERVER_ARGS),
        "local_runtime": v1_run.RUNTIME,
        "request_policy": v1_run.REQUEST_POLICY,
        "retry_policy": v1_run.RETRY_POLICY,
        "private_output": v1_run.PRIVATE_OUTPUT,
        "score_scope": "two_exposed_development_controls; no B_to_A; no safety_route",
        "token_usage": "input_tokens_preflight_only; output_tokens_not_collected",
    }


def check_protocol(path: Path, model_path: Path) -> tuple[dict, str, dict[str, dict]]:
    _check_loaded_verifier()
    raw = path.read_bytes()
    protocol = _json(raw)
    expected = _identity()
    if set(protocol) != set(expected) | {
        "frozen_code_commit",
        "source_manifest",
        "input_hashes",
        "candidate_manifest",
        "input_tokens_by_call",
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
    cases = _cases(verified_inputs["reviewed_v5_cases"])
    if protocol["candidate_manifest"] != _candidate_manifest(cases):
        raise VerificationError("candidate manifest differs")
    counts = protocol["input_tokens_by_call"]
    if (
        type(counts) is not dict
        or set(counts) != set(ORDER)
        or any(
            type(value) is not int
            or value <= 0
            or value + protocol["request_policy"]["max_tokens"] >= CONTEXT_TOKENS
            for value in counts.values()
        )
    ):
        raise VerificationError("tokenizer manifest differs")
    hashes = protocol["request_sha256_by_call"]
    if type(hashes) is not dict or set(hashes) != set(ORDER):
        raise VerificationError("request manifest differs")
    for call in ORDER:
        if hashes[call] != _request_sha(cases[call[:4]], call[-1], protocol):
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
    return protocol, _digest(raw), cases


def _journal(raw: bytes, protocol_sha: str, protocol: dict, cases: dict[str, dict]) -> list[dict]:
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise VerificationError("journal encoding differs") from error
    if len(lines) != 1 + len(ORDER):
        raise VerificationError("journal row count differs")
    rows = [_json(line.encode("utf-8")) for line in lines]
    if rows[0] != {"event": "header", "protocol_sha256": protocol_sha}:
        raise VerificationError("journal header differs")
    for row, call in zip(rows[1:], ORDER, strict=True):
        if (
            set(row) != ROW_FIELDS
            or row["event"] != "result"
            or row["call"] != call
            or row["request_sha256"] != protocol["request_sha256_by_call"][call]
            or row["request_sha256"] != _request_sha(cases[call[:4]], call[-1], protocol)
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
    path = private_dir / f"{row['call']}.json.txt"
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
    protocol, protocol_sha, cases = check_protocol(protocol_path, model_path)
    if (
        private_dir.is_symlink()
        or not private_dir.is_dir()
        or private_dir.resolve().is_relative_to(ROOT)
        or stat.S_IMODE(private_dir.stat().st_mode) != 0o700
    ):
        raise VerificationError("private directory or mode differs")
    journal_bytes = journal_path.read_bytes()
    rows = _journal(journal_bytes, protocol_sha, protocol, cases)
    expected_files = {f"{row['call']}.json.txt" for row in rows if row["raw_sha256"] is not None}
    if {entry.name for entry in private_dir.iterdir()} != expected_files:
        raise VerificationError("unexpected private response file")
    metrics = {
        "calls": len(ORDER),
        "contract_pass": 0,
        "contract_errors": 0,
        "transport_or_length_errors": 0,
        "positive_B_exact": 0,
        "positive_kind_exact": 0,
        "positive_full_match": 0,
        "negative_valid_hold": 0,
        "negative_false_nonnull": 0,
        "request_latency_ms_sum": round(sum(row["request_latency_ms"] for row in rows), 3),
    }
    per_call = []
    for row in rows:
        call = row["call"]
        case_id = call[:4]
        case = cases[case_id]
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
            case_id == "PC01"
            and valid_nonnull
            and v5_verify._same_quote(decision["subject_span"], case["gold_subject_span"])
        )
        kind_exact = decision is not None and decision["event_subject_kind"] == case["gold_kind"]
        positive_full_match = case_id == "PC01" and B_exact and kind_exact
        negative_hold = bool(
            case_id == "NC01"
            and decision is not None
            and decision["subject_span"] is None
            and kind_exact
        )
        if decision is not None:
            metrics["positive_B_exact"] += int(B_exact)
            metrics["positive_kind_exact"] += int(case_id == "PC01" and kind_exact)
            metrics["positive_full_match"] += int(positive_full_match)
            metrics["negative_valid_hold"] += int(negative_hold)
            metrics["negative_false_nonnull"] += int(case_id == "NC01" and valid_nonnull)
        per_call.append(
            {
                "call": call,
                "case_id": case_id,
                "arm": call[-1],
                "contract_pass": decision is not None,
                "contract_error_code": contract_error_code,
                "valid_nonnull": bool(valid_nonnull) if decision is not None else None,
                "source_quote_anchored": bool(valid_nonnull) if decision is not None else None,
                "positive_B_exact": B_exact if case_id == "PC01" and decision is not None else None,
                "kind_exact": bool(kind_exact) if decision is not None else None,
                "positive_full_match": (
                    bool(positive_full_match)
                    if case_id == "PC01" and decision is not None
                    else None
                ),
                "negative_valid_hold": (
                    negative_hold if case_id == "NC01" and decision is not None else None
                ),
                "negative_false_nonnull": (
                    bool(valid_nonnull) if case_id == "NC01" and decision is not None else None
                ),
                "valid_null": decision["subject_span"] is None if decision is not None else None,
                "request_latency_ms": row["request_latency_ms"],
                "input_tokens": protocol["input_tokens_by_call"][call],
            }
        )
    candidate_calls = [row for row in per_call if row["arm"] in {"B", "C"}]
    gate_pass = all(
        (
            row["positive_full_match"] is True
            if row["case_id"] == "PC01"
            else row["negative_valid_hold"] is True
        )
        for row in candidate_calls
    )
    _check_loaded_verifier()
    return {
        "claim_scope": protocol["claim_scope"],
        "protocol_sha256": protocol_sha,
        "journal_sha256": _digest(journal_bytes),
        "frozen_verifier_sha256": protocol["source_manifest"][
            "experiments/as_safety_atomic_edges_v7/verify.py"
        ],
        "replay_verifier_sha256": LOADED_VERIFIER_SHA256,
        "summary": metrics,
        "per_call": per_call,
        "candidate_availability": _gold_candidate_availability(cases),
        "candidate_gate_pass": gate_pass,
        "gold_in_requests": False,
        "official_accuracy_evaluated": False,
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
