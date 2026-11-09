"""Independently audit the frozen RE01–RE16 paired exploration result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.probe_as_safety_clause_index import validate_indexed_evidence
from scripts.probe_as_safety_evidence import route_evidence
from scripts.probe_as_safety_relation import route_relation, validate_relation

GROUPS = ("confirmed_hazard", "ambiguous_hazard", "other_source", "nonoccurring_hazard")
ROUTES = ("safety_action_required", "confirming_safety_status", "collecting_service_request")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(dataset_path: Path, protocol_path: Path, result_path: Path) -> dict:
    """Recompute routes and denominators without trusting the runner's aggregates."""
    dataset = json.loads(dataset_path.read_text())
    protocol = json.loads(protocol_path.read_text())
    result = json.loads(result_path.read_text())
    if dataset.get("review_status") != "owner_approved_for_exploration":
        raise ValueError("dataset is not approved")
    if protocol.get("dataset_sha256") != sha256(dataset_path):
        raise ValueError("protocol dataset hash differs")
    if result.get("protocol_sha256") != sha256(protocol_path):
        raise ValueError("result protocol hash differs")
    if result.get("dataset_sha256") != sha256(dataset_path):
        raise ValueError("result dataset hash differs")
    if (
        result.get("kind") != "as_safety_relation_pair_result_v1"
        or result.get("claim_scope") != "ai_authored_owner_reviewed_targeted_exploration"
    ):
        raise ValueError("result claim scope differs")
    cases, rows = dataset["cases"], result["rows"]
    if len(cases) != 16 or len(rows) != 16:
        raise ValueError("case count differs")
    if set(result) != {
        "kind",
        "claim_scope",
        "protocol_sha256",
        "dataset_sha256",
        "summary",
        "rows",
    }:
        raise ValueError("result fields differ")
    for index, (case, row) in enumerate(zip(cases, rows, strict=True)):
        if case["id"] != f"RE{index + 1:02}" or row.get("case_id") != case["id"]:
            raise ValueError("case order differs")
        if set(row) != {
            "case_id",
            "order",
            "clause_count",
            "baseline_decision",
            "baseline_route",
            "baseline_error",
            "baseline_latency_ms",
            "relation_decision",
            "relation_route",
            "relation_error",
            "relation_latency_ms",
        }:
            raise ValueError("row fields differ")
        expected_order = ["baseline", "relation"] if index % 2 == 0 else ["relation", "baseline"]
        if row["order"] != expected_order or row["clause_count"] != 2:
            raise ValueError("call order or clause count differs")
        for arm in ("baseline", "relation"):
            decision, route, error = (
                row[f"{arm}_{field}"] for field in ("decision", "route", "error")
            )
            latency = row[f"{arm}_latency_ms"]
            if type(latency) not in (int, float) or latency < 0:
                raise ValueError("invalid latency")
            if decision is None:
                if route is not None or not isinstance(error, str) or len(error) > 80:
                    raise ValueError("error row differs")
                continue
            if error is not None or not isinstance(decision, dict):
                raise ValueError("decision row differs")
            bounded = (
                validate_indexed_evidence(json.dumps(decision), 2)
                if arm == "baseline"
                else validate_relation(json.dumps(decision), 2)
            )
            expected_route = (
                route_evidence(bounded) if arm == "baseline" else route_relation(bounded)
            )
            if route != expected_route:
                raise ValueError("route differs from bounded decision")
    summary = {}
    for index, group in enumerate(GROUPS):
        part = rows[index * 4 : (index + 1) * 4]
        counts = {"denominator": 4}
        for arm in ("baseline", "relation"):
            for label, route in zip(("direct", "confirm", "normal"), ROUTES, strict=True):
                counts[f"{arm}_{label}"] = sum(row[f"{arm}_route"] == route for row in part)
            counts[f"{arm}_errors"] = sum(row[f"{arm}_error"] is not None for row in part)
        summary[group] = counts
    if result["summary"] != summary:
        raise ValueError("summary differs from case rows")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "protocol", "result"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.dataset, args.protocol, args.result), ensure_ascii=False))


if __name__ == "__main__":
    main()
