"""Independently verify the exposed Q4/Q5 safety development pair artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

from evals.structured_nlu.ai_heldout import AIHeldoutDataset
from scripts.probe_as_safety_clause_index import split_clauses

ROUTES = {
    "safety_action_required",
    "confirming_safety_status",
    "collecting_service_request",
}
ROW_KEYS = {
    "case_id",
    "clause_count",
    "evidence_index",
    "target",
    "assertion",
    "route",
    "error_type",
    "latency_ms",
}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_route(target: str, assertion: str) -> str:
    if target == "current" and assertion == "observed":
        return "safety_action_required"
    if target in {"current", "unknown"} and assertion in {"observed", "uncertain"}:
        return "confirming_safety_status"
    return "collecting_service_request"


def _summarize(rows: list[dict]) -> dict:
    def part(items: list[dict]) -> dict:
        valid = [row["latency_ms"] for row in items if row["error_type"] is None]
        return {
            "denominator": len(items),
            "contract_valid": len(valid),
            "direct_safety": sum(row["route"] == "safety_action_required" for row in items),
            "safety_confirmation": sum(row["route"] == "confirming_safety_status" for row in items),
            "normal_collection": sum(row["route"] == "collecting_service_request" for row in items),
            "errors": sum(row["error_type"] is not None for row in items),
            "median_valid_latency_ms": round(statistics.median(valid), 3) if valid else None,
        }

    return {
        "confirmed_hazard": part(rows[:12]),
        "ambiguous_hazard": part(rows[12:20]),
        "no_current_hazard": part(rows[20:]),
    }


def verify(dataset_path: Path, protocol_path: Path, result_path: Path) -> None:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    dataset = AIHeldoutDataset.model_validate_json(dataset_path.read_bytes())
    if protocol["kind"] != "as_safety_exposed_quantization_pair_protocol_v1":
        raise ValueError("unexpected protocol kind")
    if result["kind"] != "as_safety_exposed_quantization_pair_result_v1":
        raise ValueError("unexpected result kind")
    if result["claim_scope"] != "already_exposed_ai_authored_cf_development_quantization_pair_only":
        raise ValueError("unexpected claim scope")
    if result["protocol_sha256"] != _digest(protocol_path):
        raise ValueError("protocol digest differs")
    if result["dataset_sha256"] != _digest(dataset_path) or protocol["dataset_sha256"] != _digest(
        dataset_path
    ):
        raise ValueError("dataset digest differs")
    cases = dataset.cases
    if len(cases) != 32 or [case.id[-4:] for case in cases] != [f"cf{i:02}" for i in range(1, 33)]:
        raise ValueError("reviewed CF order differs")
    if set(result) != {
        "kind",
        "claim_scope",
        "protocol_sha256",
        "dataset_sha256",
        "execution_order",
        "summaries",
        "results",
    }:
        raise ValueError("unexpected result fields")
    if set(result["results"]) != {"q4", "q5"} or set(result["summaries"]) != {"q4", "q5"}:
        raise ValueError("model role set differs")
    expected_order = [
        {"case_id": case.id, "role": role}
        for index, case in enumerate(cases)
        for role in (("q4", "q5") if index % 2 == 0 else ("q5", "q4"))
    ]
    if result["execution_order"] != expected_order:
        raise ValueError("execution order differs")
    for role in ("q4", "q5"):
        rows = result["results"][role]
        if [row["case_id"] for row in rows] != [case.id for case in cases]:
            raise ValueError(f"{role} case order differs")
        for row, case in zip(rows, cases, strict=True):
            if set(row) != ROW_KEYS:
                raise ValueError("unexpected result row fields")
            count = len(split_clauses(case.user_message))
            if (
                row["clause_count"] != count
                or type(row["latency_ms"]) not in (int, float)
                or row["latency_ms"] < 0
            ):
                raise ValueError("source clause or latency differs")
            target, assertion, evidence = row["target"], row["assertion"], row["evidence_index"]
            if row["error_type"] is not None:
                if row["error_type"] not in {
                    "OSError",
                    "TimeoutError",
                    "ValueError",
                    "KeyError",
                    "TypeError",
                    "JSONDecodeError",
                    "HTTPError",
                    "URLError",
                }:
                    raise ValueError("unexpected error type")
                if any(
                    row[key] is not None
                    for key in ("route", "target", "assertion", "evidence_index")
                ):
                    raise ValueError("failed request has a decision")
                continue
            if target not in {"current", "other", "unknown", "none"} or assertion not in {
                "observed",
                "uncertain",
                "negated_or_hypothetical",
                "none",
            }:
                raise ValueError("invalid target or assertion")
            if evidence is None:
                if (target, assertion) != ("none", "none"):
                    raise ValueError("empty evidence fields disagree")
            elif (
                type(evidence) is not int
                or not 1 <= evidence <= count
                or "none" in (target, assertion)
            ):
                raise ValueError("evidence index differs from source")
            if row["route"] not in ROUTES or row["route"] != _expected_route(target, assertion):
                raise ValueError("route differs from bounded decision")
        if result["summaries"][role] != _summarize(rows):
            raise ValueError(f"{role} summary differs")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    verify(args.dataset, args.protocol, args.result)
    print("verified exposed Q4/Q5 development pair")


if __name__ == "__main__":
    main()
