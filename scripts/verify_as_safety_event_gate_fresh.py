"""Check source indices, decisions, privacy boundary, and aggregates independently."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.probe_as_safety_clause_index import split_clauses
from scripts.probe_as_safety_event_gate import gate_direct_safety
from scripts.probe_as_safety_evidence import route_evidence

ROUTES = {"safety_action_required", "confirming_safety_status", "collecting_service_request"}
ROW_KEYS = {
    "case_id",
    "clause_count",
    "evidence_index",
    "target",
    "assertion",
    "model_route",
    "gate_route",
    "gate_reason",
    "error_type",
    "latency_ms",
}
ERROR_TYPES = {
    "OSError",
    "TimeoutError",
    "ValueError",
    "KeyError",
    "TypeError",
    "JSONDecodeError",
    "HTTPError",
    "URLError",
}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _summary(rows: list[dict]) -> dict:
    groups = (
        ("confirmed_hazard", 0, 8),
        ("ambiguous_hazard", 8, 16),
        ("other_source", 16, 24),
        ("nonoccurring_hazard", 24, 32),
    )
    return {
        name: {
            "denominator": len(part := rows[start:stop]),
            "model_direct": sum(row["model_route"] == "safety_action_required" for row in part),
            "gate_direct": sum(row["gate_route"] == "safety_action_required" for row in part),
            "gate_confirmation": sum(
                row["gate_route"] == "confirming_safety_status" for row in part
            ),
            "gate_normal": sum(row["gate_route"] == "collecting_service_request" for row in part),
            "errors": sum(row["error_type"] is not None for row in part),
        }
        for name, start, stop in groups
    }


def verify(dataset_path: Path, protocol_path: Path, result_path: Path) -> None:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if protocol.get("kind") != "as_safety_event_gate_fresh_protocol_v1":
        raise ValueError("unexpected protocol kind")
    if result.get("kind") != "as_safety_event_gate_fresh_result_v1":
        raise ValueError("unexpected result kind")
    if result.get("claim_scope") != "ai_authored_owner_reviewed_targeted_exploration":
        raise ValueError("claim scope differs")
    if result.get("protocol_sha256") != _digest(protocol_path):
        raise ValueError("protocol digest differs")
    if result.get("dataset_sha256") != _digest(dataset_path) or protocol[
        "dataset_sha256"
    ] != _digest(dataset_path):
        raise ValueError("dataset digest differs")
    if set(result) != {
        "kind",
        "claim_scope",
        "protocol_sha256",
        "dataset_sha256",
        "summary",
        "rows",
    }:
        raise ValueError("unexpected result fields")
    if (
        dataset.get("kind") != "as_safety_event_gate_ai_reviewed_v1"
        or dataset.get("provenance") != "ai_authored"
        or dataset.get("review_status") != "owner_approved_for_exploration"
    ):
        raise ValueError("reviewed input provenance differs")
    cases = dataset.get("cases")
    rows = result["rows"]
    if (
        not isinstance(cases, list)
        or not isinstance(rows, list)
        or len(cases) != len(rows)
        or len(rows) != 32
    ):
        raise ValueError("result denominator differs")
    expected_routes = (
        ["safety_action_required"] * 8
        + ["confirming_safety_status"] * 8
        + ["collecting_service_request"] * 16
    )
    if [case.get("expected_route") for case in cases] != expected_routes:
        raise ValueError("reviewed route order differs")
    for number, (case, row) in enumerate(zip(cases, rows, strict=True), 1):
        if set(case) != {"id", "user_message", "expected_route"} or case["id"] != f"EG{number:02}":
            raise ValueError("reviewed case fields or order differ")
        if set(row) != ROW_KEYS or row["case_id"] != case["id"]:
            raise ValueError("result row fields or order differ")
        clauses = split_clauses(case["user_message"])
        if row["clause_count"] != len(clauses):
            raise ValueError("source clause count differs")
        if (
            type(row["latency_ms"]) not in (int, float)
            or not math.isfinite(row["latency_ms"])
            or row["latency_ms"] < 0
        ):
            raise ValueError("latency is invalid")
        if row["error_type"] is not None:
            if row["error_type"] not in ERROR_TYPES or any(
                row[key] is not None
                for key in (
                    "evidence_index",
                    "target",
                    "assertion",
                    "model_route",
                    "gate_route",
                    "gate_reason",
                )
            ):
                raise ValueError("failed request has invalid decision")
            continue
        target, assertion, index = row["target"], row["assertion"], row["evidence_index"]
        if target not in {"current", "other", "unknown", "none"} or assertion not in {
            "observed",
            "uncertain",
            "negated_or_hypothetical",
            "none",
        }:
            raise ValueError("model decision enum differs")
        if index is None:
            if (target, assertion) != ("none", "none"):
                raise ValueError("empty evidence fields disagree")
        elif (
            type(index) is not int
            or not 1 <= index <= len(clauses)
            or "none" in (target, assertion)
        ):
            raise ValueError("source evidence index differs")
        model_route = route_evidence({"target": target, "assertion": assertion})
        gate = gate_direct_safety(
            case["user_message"], {"route": model_route, "evidence_index": index}
        )
        if (
            row["model_route"] != model_route
            or row["gate_route"] != gate.route
            or row["gate_reason"] != gate.reason
            or gate.route not in ROUTES
        ):
            raise ValueError("saved route differs from frozen contract")
    if result["summary"] != _summary(rows):
        raise ValueError("saved summary differs from rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    verify(args.dataset, args.protocol, args.result)
    print("verified A/S event gate exploratory result")


if __name__ == "__main__":
    main()
