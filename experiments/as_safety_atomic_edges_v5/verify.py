"""Independently replay the two private E→B control responses."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
import subprocess
from datetime import date
from pathlib import Path

from experiments.as_safety_atomic_edges_v1 import run as v1_run
from experiments.as_safety_atomic_edges_v1 import verify as v1_verify
from experiments.as_safety_atomic_edges_v4 import run as v4_run
from experiments.as_safety_atomic_edges_v4 import verify as v4_verify

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout/as-safety-eb-controls-v5-cases.json"
METHOD = ROOT / "docs/portfolio/nlu_safety_atomic_edge_controls_v5_method.md"
INPUTS = {"control_cases": DATA, "method": METHOD}
SOURCE_PATHS = v4_run.SOURCE_PATHS | {
    "experiments/as_safety_atomic_edges_v5/__init__.py",
    "experiments/as_safety_atomic_edges_v5/run.py",
    "experiments/as_safety_atomic_edges_v5/verify.py",
    "tests/test_as_safety_atomic_edge_controls_v5.py",
}
POST_RUN_REPLAY_SOURCES = {
    "experiments/as_safety_atomic_edges_v5/run.py",
    "experiments/as_safety_atomic_edges_v5/verify.py",
    "tests/test_as_safety_atomic_edge_controls_v5.py",
}
CASE_IDS = ("PC01", "NC01")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
ROW_FIELDS = {
    "event",
    "case_id",
    "request_sha256",
    "finish_reason",
    "error_code",
    "http_status",
    "raw_sha256",
    "raw_bytes",
    "request_latency_ms",
}
TRANSPORT_CODES = {
    "redirect",
    "request_too_large",
    "http_status",
    "http_error",
    "network_error",
    "timeout",
    "response_too_large",
    "invalid_response_json",
    "response_fields_invalid",
}
CONTRACT_ERRORS = v4_verify.CONTRACT_ERROR_CODES


class VerificationError(ValueError):
    """A bounded error that does not quote private input or output."""


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


def _git(*args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=ROOT, check=True, capture_output=True).stdout


def _frozen(commit: str, relative: str) -> bytes:
    if (
        type(commit) is not str
        or not COMMIT_RE.fullmatch(commit)
        or relative.startswith("/")
        or ".." in Path(relative).parts
    ):
        raise VerificationError("frozen reference invalid")
    return _git("show", f"{commit}:{relative}")


def _json(raw: bytes) -> dict:
    try:
        parsed = v1_verify._json(raw.decode("utf-8"))
    except (UnicodeDecodeError, v1_verify.VerificationError) as error:
        raise VerificationError("JSON invalid") from error
    if type(parsed) is not dict:
        raise VerificationError("JSON object required")
    return parsed


def _source_cases(raw: bytes) -> dict[str, dict]:
    payload = _json(raw)
    if (
        set(payload) != {"kind", "provenance", "review_status", "review_date", "cases"}
        or payload["kind"] != "as_safety_eb_controls_v5_cases_v1"
        or payload["provenance"] != "ai_authored_development_control"
        or payload["review_status"] != "user_approved_for_development_probe"
        or type(payload["review_date"]) is not str
        or not DATE_RE.fullmatch(payload["review_date"])
        or type(payload["cases"]) is not list
        or len(payload["cases"]) != 2
    ):
        raise VerificationError("reviewed controls differ")
    try:
        date.fromisoformat(payload["review_date"])
    except ValueError as error:
        raise VerificationError("review date invalid") from error
    cases = {}
    expected_fields = {
        "case_id",
        "user_message",
        "product_index",
        "target_mention",
        "event_span",
        "occurrence",
        "gold_subject_span",
        "gold_kind",
    }
    for index, case in enumerate(payload["cases"]):
        if (
            type(case) is not dict
            or set(case) != expected_fields
            or case["case_id"] != CASE_IDS[index]
        ):
            raise VerificationError("control identity differs")
        if (
            type(case["user_message"]) is not str
            or not case["user_message"].strip()
            or type(case["product_index"]) is not int
            or type(case["target_mention"]) is not str
            or not case["target_mention"].strip()
            or case["occurrence"] != "observed"
        ):
            raise VerificationError("control source invalid")
        clauses = v1_verify._clauses(case["user_message"])
        try:
            event = v1_verify._span(case["event_span"], clauses)
            target = v1_verify._span(
                {"clause_index": case["product_index"], "quote": case["target_mention"]},
                clauses,
            )
            gold = v1_verify._span(case["gold_subject_span"], clauses)
        except v1_verify.VerificationError as error:
            raise VerificationError("control span invalid") from error
        if event is None or target is None:
            raise VerificationError("control source span missing")
        if case["case_id"] == "PC01":
            if gold is None or case["gold_kind"] != "location":
                raise VerificationError("positive control label invalid")
        elif gold is not None or case["gold_kind"] != "unresolved":
            raise VerificationError("negative control label invalid")
        cases[case["case_id"]] = case
    return cases


def _request_sha(case: dict, protocol: dict) -> str:
    """Rebuild the wire body using v4's independent replay, never v5 runner code."""
    source = {
        "user_message": case["user_message"],
        "target": {"clause_index": case["product_index"], "quote": case["target_mention"]},
        "events": [{"event_span": case["event_span"], "occurrence": case["occurrence"]}],
    }
    return v4_verify._request_sha(source, "variant", protocol)


def _expected_identity() -> dict:
    return {
        "kind": "as_safety_eb_controls_v5_development_v1",
        "claim_scope": "ai_authored_user_reviewed_development_controls_only",
        "case_ids": list(CASE_IDS),
        "call_order": list(CASE_IDS),
        "response_format": "v4_subject_only_two_field_schema_constrained_json",
        "model_sha256": v1_run.MODEL_SHA,
        "server_image_digest": v1_run.IMAGE,
        "container_name": "as-safety-eb-controls-v5",
        "endpoint": v1_run.ENDPOINT,
        "model_id": v1_run.MODEL_ID,
        "server_args": list(v1_run.SERVER_ARGS),
        "local_runtime": v1_run.RUNTIME,
        "request_policy": v1_run.REQUEST_POLICY,
        "retry_policy": v1_run.RETRY_POLICY,
        "private_output": v1_run.PRIVATE_OUTPUT,
        "score_scope": "two development controls; no B_to_A; no safety route; no official accuracy",
        "token_usage": "not_collected_by_completion_transport",
    }


def check_protocol(path: Path, model_path: Path) -> tuple[dict, str, dict[str, dict]]:
    _check_loaded_verifier()
    raw = path.read_bytes()
    protocol = _json(raw)
    identity = _expected_identity()
    if (
        set(protocol)
        != set(identity)
        | {"frozen_code_commit", "source_manifest", "input_hashes", "request_sha256_by_call"}
        or any(protocol.get(key) != value for key, value in identity.items())
        or type(protocol["request_policy"]) is not dict
        or type(protocol["request_policy"].get("timeout_seconds")) is not int
    ):
        raise VerificationError("protocol identity differs")
    if not model_path.is_file() or _digest_file(model_path) != v1_run.MODEL_SHA:
        raise VerificationError("model file digest differs")
    commit = protocol["frozen_code_commit"]
    manifest = protocol["source_manifest"]
    if type(commit) is not str or not COMMIT_RE.fullmatch(commit):
        raise VerificationError("frozen commit differs")
    if type(manifest) is not dict or set(manifest) != SOURCE_PATHS:
        raise VerificationError("source manifest differs")
    for relative, expected_sha in manifest.items():
        frozen = _frozen(commit, relative)
        if (
            type(expected_sha) is not str
            or not SHA_RE.fullmatch(expected_sha)
            or _digest(frozen) != expected_sha
            or (
                relative not in POST_RUN_REPLAY_SOURCES and (ROOT / relative).read_bytes() != frozen
            )
        ):
            raise VerificationError("source manifest differs")
    inputs = protocol["input_hashes"]
    if type(inputs) is not dict or set(inputs) != set(INPUTS):
        raise VerificationError("input manifest differs")
    verified_inputs = {}
    for key, source in INPUTS.items():
        frozen = _frozen(commit, source.relative_to(ROOT).as_posix())
        current = source.read_bytes()
        if (
            type(inputs[key]) is not str
            or not SHA_RE.fullmatch(inputs[key])
            or _digest(frozen) != inputs[key]
            or current != frozen
        ):
            raise VerificationError(f"input differs: {key}")
        verified_inputs[key] = current
    cases = _source_cases(verified_inputs["control_cases"])
    hashes = protocol["request_sha256_by_call"]
    if type(hashes) is not dict or set(hashes) != set(CASE_IDS):
        raise VerificationError("request manifest differs")
    for key in CASE_IDS:
        if hashes[key] != _request_sha(cases[key], protocol):
            raise VerificationError("frozen request differs")
    if _git("show", f"HEAD:{path.resolve().relative_to(ROOT).as_posix()}") != raw:
        raise VerificationError("protocol is not committed")
    _check_loaded_verifier()
    return protocol, _digest(raw), cases


def _journal(raw: bytes, protocol_sha: str, cases: dict[str, dict], protocol: dict) -> list[dict]:
    rows = []
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise VerificationError("journal encoding differs") from error
    for line in lines:
        if not line.strip():
            raise VerificationError("blank journal line")
        parsed = _json(line.encode("utf-8"))
        rows.append(parsed)
    if len(rows) != 3 or rows[0] != {"event": "header", "protocol_sha256": protocol_sha}:
        raise VerificationError("journal header or length differs")
    for row, case_id in zip(rows[1:], CASE_IDS, strict=True):
        if (
            set(row) != ROW_FIELDS
            or row["event"] != "result"
            or row["case_id"] != case_id
            or row["request_sha256"] != protocol["request_sha256_by_call"][case_id]
            or row["request_sha256"] != _request_sha(cases[case_id], protocol)
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
                and error in TRANSPORT_CODES
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
    path = private_dir / f"{row['case_id']}.json.txt"
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise VerificationError("private response file or mode differs")
    content = path.read_bytes()
    if _digest(content) != row["raw_sha256"] or len(content) != row["raw_bytes"]:
        raise VerificationError("private response digest differs")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise VerificationError("private response encoding differs") from error


def _same_quote(left: dict | None, right: dict | None) -> bool:
    if left is None or right is None:
        return left is right
    return left["clause_index"] == right["clause_index"] and left["quote"] == right["quote"]


def verify_result(
    protocol_path: Path, model_path: Path, journal_path: Path, private_dir: Path
) -> dict:
    protocol, protocol_sha, cases = check_protocol(protocol_path, model_path)
    if (
        private_dir.is_symlink()
        or not private_dir.is_dir()
        or private_dir.resolve().is_relative_to(ROOT)
        or stat.S_IMODE(private_dir.stat().st_mode) != 0o700
    ):
        raise VerificationError("private directory or mode differs")
    journal_bytes = journal_path.read_bytes()
    rows = _journal(journal_bytes, protocol_sha, cases, protocol)
    expected_files = {f"{row['case_id']}.json.txt" for row in rows if row["raw_sha256"] is not None}
    if {entry.name for entry in private_dir.iterdir()} != expected_files:
        raise VerificationError("unexpected private response file")
    metrics = {
        "calls": 2,
        "contract_pass": 0,
        "contract_errors": 0,
        "transport_or_length_errors": 0,
        "positive_valid_nonnull": 0,
        "positive_quote_anchored": 0,
        "positive_B_exact": 0,
        "positive_kind_exact": 0,
        "positive_evaluable": False,
        "negative_correct_abstention": 0,
        "negative_false_resolution": 0,
        "negative_evaluable": False,
        "request_latency_ms_sum": round(sum(row["request_latency_ms"] for row in rows), 3),
    }
    per_case = []
    for row in rows:
        case = cases[row["case_id"]]
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
                contract_error_code = CONTRACT_ERRORS.get(str(error), "contract_invalid")
            else:
                metrics["contract_pass"] += 1
        if case["case_id"] == "PC01":
            metrics["positive_evaluable"] = decision is not None
            if decision is not None:
                # replay_subject_only accepts a nonnull quote only if it is
                # uniquely anchored in the source text.
                metrics["positive_valid_nonnull"] = int(decision["subject_span"] is not None)
                metrics["positive_quote_anchored"] = int(decision["subject_span"] is not None)
                metrics["positive_B_exact"] = int(
                    _same_quote(decision["subject_span"], case["gold_subject_span"])
                )
                metrics["positive_kind_exact"] = int(
                    decision["event_subject_kind"] == case["gold_kind"]
                )
        else:
            metrics["negative_evaluable"] = decision is not None
            if decision is not None:
                metrics["negative_correct_abstention"] = int(
                    decision["event_subject_kind"] == "unresolved"
                    and decision["subject_span"] is None
                )
                metrics["negative_false_resolution"] = int(
                    decision["event_subject_kind"] != "unresolved"
                )
        per_case.append(
            {
                "case_id": row["case_id"],
                "contract_pass": decision is not None,
                "contract_error_code": contract_error_code,
                "valid_nonnull": (
                    bool(metrics["positive_valid_nonnull"])
                    if case["case_id"] == "PC01" and decision is not None
                    else None
                ),
                "quote_anchored": (
                    bool(metrics["positive_quote_anchored"])
                    if case["case_id"] == "PC01" and decision is not None
                    else None
                ),
                "B_exact": (
                    bool(metrics["positive_B_exact"])
                    if case["case_id"] == "PC01" and decision is not None
                    else None
                ),
                "kind_exact": (
                    bool(metrics["positive_kind_exact"])
                    if case["case_id"] == "PC01" and decision is not None
                    else None
                ),
                "valid_abstention": (
                    bool(metrics["negative_correct_abstention"])
                    if case["case_id"] == "NC01" and decision is not None
                    else None
                ),
                "false_resolution": (
                    bool(metrics["negative_false_resolution"])
                    if case["case_id"] == "NC01" and decision is not None
                    else None
                ),
                "request_latency_ms": row["request_latency_ms"],
            }
        )
    _check_loaded_verifier()
    gate = (
        metrics["contract_pass"] == 2
        and metrics["positive_valid_nonnull"] == 1
        and metrics["negative_correct_abstention"] == 1
    )
    return {
        "claim_scope": protocol["claim_scope"],
        "protocol_sha256": protocol_sha,
        "journal_sha256": _digest(journal_bytes),
        "frozen_verifier_sha256": protocol["source_manifest"][
            "experiments/as_safety_atomic_edges_v5/verify.py"
        ],
        "replay_verifier_sha256": LOADED_VERIFIER_SHA256,
        "summary": metrics,
        "per_case": per_case,
        "control_gate_pass": gate,
        "B_to_A_evaluated": False,
        "final_safety_route_evaluated": False,
        "official_accuracy_or_improvement_claim": False,
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
