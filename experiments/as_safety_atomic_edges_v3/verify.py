"""Independently replay private ES E→B response-format probe outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
import subprocess
from pathlib import Path

from experiments.as_safety_atomic_edges_v1 import verify as v1
from experiments.as_safety_atomic_edges_v2 import verify as v2

ROOT = Path(__file__).resolve().parents[2]
INPUTS = {
    **v1.INPUTS,
    "method_v2": ROOT / "docs/portfolio/nlu_safety_atomic_edge_abstention_v2_method.md",
    "method_v3": ROOT / "docs/portfolio/nlu_safety_atomic_edge_format_v3_method.md",
}
SOURCE_PATHS = v2.SOURCE_PATHS | {
    "experiments/as_safety_atomic_edges_v3/__init__.py",
    "experiments/as_safety_atomic_edges_v3/run.py",
    "experiments/as_safety_atomic_edges_v3/verify.py",
}
CASE_IDS = ("ES01", "ES03", "ES09", "ES17", "ES18")
ORDER = (
    ("ES01", "baseline"),
    ("ES01", "variant"),
    ("ES03", "variant"),
    ("ES03", "baseline"),
    ("ES09", "baseline"),
    ("ES09", "variant"),
    ("ES17", "variant"),
    ("ES17", "baseline"),
    ("ES18", "baseline"),
    ("ES18", "variant"),
)
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
ROW_FIELDS = {
    "event",
    "case_id",
    "event_index",
    "condition",
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
REFERENCE_PROTOCOL_SHA256 = "fa7a2f574220e7fb92275277895d5aa14c14f12434cf715c7fdb8aa8702de56c"
REFERENCE_JOURNAL_SHA256 = "804c1c1f64545e7f883ed783ffecdd67b8d89908dd3b055104e24b43925c0b3b"
CONTRACT_ERROR_CODES = {
    "invalid JSON": "invalid_json",
    "duplicate JSON key": "duplicate_json_key",
    "nonfinite JSON value": "nonfinite_json_value",
    "output fields differ": "output_fields_invalid",
    "event subject kind invalid": "subject_kind_invalid",
    "quote fields invalid": "quote_fields_invalid",
    "quote index invalid": "quote_index_invalid",
    "quote blank or invalid": "quote_blank_or_invalid",
    "quote is not uniquely anchored": "quote_not_anchored",
    "unresolved spans inconsistent": "unresolved_spans_inconsistent",
    "direct evidence does not contain event and subject": "direct_evidence_invalid",
}


class VerificationError(ValueError):
    """Bounded replay failure without private content in the error text."""


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _git(*args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=ROOT, check=True, capture_output=True).stdout


def _frozen(commit: str, relative: str) -> bytes:
    if not COMMIT_RE.fullmatch(commit) or relative.startswith("/") or ".." in Path(relative).parts:
        raise VerificationError("frozen reference invalid")
    return _git("show", f"{commit}:{relative}")


def check_protocol(path: Path, model_path: Path) -> tuple[dict, str, dict[str, bytes]]:
    raw = path.read_bytes()
    try:
        protocol = v1._json(raw.decode("utf-8"))
    except (UnicodeDecodeError, v1.VerificationError) as error:
        raise VerificationError("protocol JSON invalid") from error
    expected_keys = {
        "kind",
        "claim_scope",
        "case_ids",
        "call_order",
        "baseline_response_format",
        "variant_response_format",
        "historical_v2_protocol_sha256",
        "model_sha256",
        "server_image_digest",
        "container_name",
        "endpoint",
        "model_id",
        "server_args",
        "local_runtime",
        "request_policy",
        "retry_policy",
        "private_output",
        "score_scope",
        "frozen_code_commit",
        "source_manifest",
        "input_hashes",
        "request_sha256_by_call",
    }
    if type(protocol) is not dict or set(protocol) != expected_keys:
        raise VerificationError("protocol fields differ")
    expected = {
        "kind": "as_safety_atomic_edge_response_format_v3_development_v1",
        "claim_scope": "already_exposed_ai_authored_user_reviewed_es_paired_development_probe_only",
        "case_ids": list(CASE_IDS),
        "call_order": [list(pair) for pair in ORDER],
        "baseline_response_format": "json_object_with_schema",
        "variant_response_format": "plain_json_object",
        "historical_v2_protocol_sha256": REFERENCE_PROTOCOL_SHA256,
        "model_sha256": v1.MODEL_SHA,
        "server_image_digest": v1.IMAGE,
        "container_name": "as-safety-eb-format-v3",
        "endpoint": v1.ENDPOINT,
        "model_id": v1.MODEL_ID,
        "server_args": list(v1.SERVER_ARGS),
        "local_runtime": v1.RUNTIME,
        "request_policy": v1.REQUEST_POLICY,
        "retry_policy": "no_retry_manual_audit_on_interruption",
        "private_output": "outside_repository_mode_0700_files_0600",
        "score_scope": "E_to_B_only; no B_to_A; no safety_route; no official_accuracy",
    }
    if any(protocol[key] != value for key, value in expected.items()):
        raise VerificationError("protocol identity differs")
    if (
        type(protocol["request_policy"]) is not dict
        or type(protocol["request_policy"].get("timeout_seconds")) is not int
    ):
        raise VerificationError("request timeout type differs")
    if not model_path.is_file() or _digest_file(model_path) != v1.MODEL_SHA:
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
                relative
                not in {
                    "experiments/as_safety_atomic_edges_v3/run.py",
                    "experiments/as_safety_atomic_edges_v3/verify.py",
                }
                and (ROOT / relative).read_bytes() != frozen
            )
        ):
            raise VerificationError(f"source manifest differs: {relative}")
    hashes = protocol["input_hashes"]
    if type(hashes) is not dict or set(hashes) != set(INPUTS):
        raise VerificationError("input manifest differs")
    verified = {}
    for key, source in INPUTS.items():
        frozen = _frozen(commit, source.relative_to(ROOT).as_posix())
        current = source.read_bytes()
        expected_sha = hashes[key]
        if (
            type(expected_sha) is not str
            or not SHA_RE.fullmatch(expected_sha)
            or _digest(frozen) != expected_sha
            or current != frozen
        ):
            raise VerificationError(f"input differs: {key}")
        verified[key] = current
    request_hashes = protocol["request_sha256_by_call"]
    if type(request_hashes) is not dict or set(request_hashes) != {
        f"{case_id}:{condition}" for case_id, condition in ORDER
    }:
        raise VerificationError("frozen request manifest differs")
    source_cases = _source_cases(verified)
    for case_id, condition in ORDER:
        key = f"{case_id}:{condition}"
        if request_hashes[key] != _request_sha(source_cases[case_id], condition, protocol):
            raise VerificationError("frozen request differs from reviewed input")
    historical_raw = (
        ROOT
        / "evals/structured_nlu/data/ai_heldout/as-safety-eb-abstention-v2-development-protocol.json"
    ).read_bytes()
    if _digest(historical_raw) != REFERENCE_PROTOCOL_SHA256:
        raise VerificationError("historical protocol digest differs")
    historical = v1._json(historical_raw.decode("utf-8"))
    if historical.get("kind") != "as_safety_atomic_edge_abstention_v2_development_v1":
        raise VerificationError("historical protocol identity differs")
    for case_id in CASE_IDS:
        if (
            request_hashes[f"{case_id}:baseline"]
            != historical["request_sha256_by_call"][f"{case_id}:baseline"]
        ):
            raise VerificationError("baseline request differs from historical v2")
    if _git("show", f"HEAD:{path.resolve().relative_to(ROOT).as_posix()}") != raw:
        raise VerificationError("protocol is not committed")
    return protocol, _digest(raw), verified


def _source_cases(verified: dict[str, bytes]) -> dict[str, dict]:
    # Read only reviewed input spans. Gold columns stay in the scoring path below.
    payload = v1._json(verified["dataset"].decode("utf-8"))
    selected = {case["id"]: case for case in payload["cases"] if case["id"] in CASE_IDS}
    if set(selected) != set(CASE_IDS):
        raise VerificationError("selected source cases differ")
    for case_id, case in selected.items():
        if case["events"][0]["occurrence"] not in {"observed", "uncertain"}:
            raise VerificationError(f"selected event is not callable: {case_id}")
    return selected


def _request_sha(case: dict, condition: str, protocol: dict) -> str:
    """Rebuild the request from reviewed source fields without importing candidate code."""
    from experiments.as_safety_atomic_edges_v1.event_owner import (
        event_owner_messages,
        event_owner_schema,
    )

    event = case["events"][0]
    messages = event_owner_messages(
        case["user_message"],
        event["event_span"],
        event["occurrence"],
        product_index=case["target"]["clause_index"],
        target_mention=case["target"]["quote"],
    )
    if condition not in {"baseline", "variant"}:
        raise VerificationError("condition differs")
    policy = protocol["request_policy"]
    payload = {
        "model": protocol["model_id"],
        "messages": messages,
        "max_tokens": policy["max_tokens"],
        "temperature": policy["temperature"],
        "repeat_penalty": policy["repeat_penalty"],
        "stop": policy["stop"],
        "seed": policy["seed"],
        "response_format": (
            {"type": "json_object", "schema": event_owner_schema(case["user_message"])}
            if condition == "baseline"
            else {"type": "json_object"}
        ),
    }
    return _digest(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"))


def _journal(path: Path, protocol_sha: str, sources: dict[str, dict], protocol: dict) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            raise VerificationError("blank journal line")
        parsed = v1._json(line)
        if type(parsed) is not dict:
            raise VerificationError("journal row invalid")
        rows.append(parsed)
    if len(rows) != 11 or rows[0] != {"event": "header", "protocol_sha256": protocol_sha}:
        raise VerificationError("journal header or length differs")
    for row, (case_id, condition) in zip(rows[1:], ORDER, strict=True):
        if (
            set(row) != ROW_FIELDS
            or row["event"] != "result"
            or row["case_id"] != case_id
            or type(row["event_index"]) is not int
            or row["event_index"] != 1
            or row["condition"] != condition
            or row["request_sha256"] != _request_sha(sources[case_id], condition, protocol)
            or row["request_sha256"] != protocol["request_sha256_by_call"][f"{case_id}:{condition}"]
        ):
            raise VerificationError("journal event or request identity differs")
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
    path = private_dir / f"{row['case_id']}-{row['condition']}.json.txt"
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
    protocol_path: Path,
    model_path: Path,
    journal_path: Path,
    private_dir: Path,
    reference_protocol_path: Path,
    reference_journal_path: Path,
    reference_private_dir: Path,
) -> dict:
    if (
        _digest_file(reference_protocol_path) != REFERENCE_PROTOCOL_SHA256
        or _digest_file(reference_journal_path) != REFERENCE_JOURNAL_SHA256
    ):
        raise VerificationError("historical reference digest differs")
    reference_protocol, reference_sha, reference_inputs = v2.check_protocol(
        reference_protocol_path, model_path
    )
    reference_sources = v2._source_cases(reference_inputs)
    if (
        reference_private_dir.is_symlink()
        or reference_private_dir.resolve().is_relative_to(ROOT)
        or stat.S_IMODE(reference_private_dir.stat().st_mode) != 0o700
    ):
        raise VerificationError("historical private directory or mode differs")
    reference_rows = {
        row["case_id"]: row
        for row in v2._journal(
            reference_journal_path, reference_sha, reference_sources, reference_protocol
        )
        if row["condition"] == "baseline"
    }
    if set(reference_rows) != set(CASE_IDS):
        raise VerificationError("historical reference cases differ")
    protocol, protocol_sha, verified = check_protocol(protocol_path, model_path)
    if (
        private_dir.is_symlink()
        or private_dir.resolve().is_relative_to(ROOT)
        or stat.S_IMODE(private_dir.stat().st_mode) != 0o700
    ):
        raise VerificationError("private response directory or mode differs")
    source_cases = _source_cases(verified)
    rows = _journal(journal_path, protocol_sha, source_cases, protocol)
    if {entry.name for entry in private_dir.iterdir()} != {
        f"{row['case_id']}-{row['condition']}.json.txt"
        for row in rows
        if row["raw_sha256"] is not None
    }:
        raise VerificationError("unexpected private response file")
    scored_cases = {
        case["id"]: case
        for case in v1.load_scoring_cases(INPUTS["dataset"], raw=verified["dataset"])
    }
    labels = v1.load_edge_labels(INPUTS["edge_review"], raw=verified["edge_review"])
    if any((case_id, 1) not in labels for case_id in CASE_IDS):
        raise VerificationError("selected reviewed E→B label missing")
    summary = {}
    per_case = []
    baseline_reproduced = {}
    for condition in ("baseline", "variant"):
        selected = [row for row in rows if row["condition"] == condition]
        metrics = {
            "calls": 5,
            "contract_pass": 0,
            "abstentions": 0,
            "B_exact_resolved": 0,
            "B_resolved_denominator": 4,
            "kind_exact": 0,
            "evidence_exact": 0,
            "resolved_evidence_exact": 0,
            "resolved_evidence_denominator": 4,
            "ES17_correct_abstention": 0,
            "ES17_false_resolution": 0,
            "ES17_evaluable": False,
            "contract_errors": 0,
            "transport_or_length_errors": 0,
        }
        for row in selected:
            case_id = row["case_id"]
            source = source_cases[case_id]
            event = source["events"][0]
            gold = scored_cases[case_id]["events"][0]["hazard_owner_span"]
            label = labels[(case_id, 1)]
            raw = _raw(private_dir, row)
            if condition == "baseline":
                reference_raw = v2._raw(reference_private_dir, reference_rows[case_id])
                baseline_reproduced[case_id] = (
                    raw is not None
                    and reference_raw is not None
                    and raw == reference_raw
                    and row["raw_sha256"] == reference_rows[case_id]["raw_sha256"]
                )
            decision = None
            contract_error_code = None
            if row["error_code"] is not None or row["finish_reason"] != "stop":
                metrics["transport_or_length_errors"] += 1
            elif raw is not None:
                try:
                    decision = v1.replay_event_owner(
                        raw, source["user_message"], event["event_span"]
                    )
                except v1.VerificationError as error:
                    metrics["contract_errors"] += 1
                    contract_error_code = CONTRACT_ERROR_CODES.get(str(error), "contract_invalid")
                else:
                    metrics["contract_pass"] += 1
                    metrics["abstentions"] += decision["event_subject_kind"] == "unresolved"
                    metrics["kind_exact"] += (
                        decision["event_subject_kind"] == label["event_subject_kind"]
                    )
                    metrics["evidence_exact"] += _same_quote(
                        decision["event_subject_evidence_span"],
                        label["event_subject_evidence_span"],
                    )
                    if label["event_subject_evidence_span"] is not None:
                        metrics["resolved_evidence_exact"] += _same_quote(
                            decision["event_subject_evidence_span"],
                            label["event_subject_evidence_span"],
                        )
            if gold is None:
                if case_id != "ES17":
                    raise VerificationError("unexpected unresolved reference")
                metrics["ES17_evaluable"] = decision is not None
                metrics["ES17_correct_abstention"] += (
                    decision is not None and decision["event_subject_kind"] == "unresolved"
                )
                metrics["ES17_false_resolution"] += (
                    decision is not None and decision["event_subject_kind"] != "unresolved"
                )
            elif decision is not None:
                metrics["B_exact_resolved"] += _same_quote(decision["subject_span"], gold)
            per_case.append(
                {
                    "case_id": case_id,
                    "condition": condition,
                    "contract_pass": decision is not None,
                    "contract_error_code": contract_error_code,
                    "abstained": decision is not None
                    and decision["event_subject_kind"] == "unresolved",
                    "B_exact_resolved": gold is not None
                    and decision is not None
                    and _same_quote(decision["subject_span"], gold),
                    "kind_exact": decision is not None
                    and decision["event_subject_kind"] == label["event_subject_kind"],
                    "evidence_exact": decision is not None
                    and _same_quote(
                        decision["event_subject_evidence_span"],
                        label["event_subject_evidence_span"],
                    ),
                }
            )
        summary[condition] = metrics
    return {
        "claim_scope": protocol["claim_scope"],
        "protocol_sha256": protocol_sha,
        "replay_verifier_sha256": _digest_file(Path(__file__)),
        "summary": summary,
        "historical_baseline_reproduced": baseline_reproduced,
        "historical_baseline_all_reproduced": all(baseline_reproduced.values()),
        "causal_interpretation_requires_reproduced_baseline": True,
        "paired_cases": per_case,
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
    parser.add_argument("--reference-protocol", required=True, type=Path)
    parser.add_argument("--reference-journal", required=True, type=Path)
    parser.add_argument("--reference-private-dir", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            verify_result(
                args.protocol,
                args.model_path,
                args.journal,
                args.private_dir,
                args.reference_protocol,
                args.reference_journal,
                args.reference_private_dir,
            ),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
