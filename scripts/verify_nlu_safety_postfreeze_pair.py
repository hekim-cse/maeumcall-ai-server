"""Independently validate a saved A/S postfreeze safety comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from evals.structured_nlu.ai_heldout import AIHeldoutDataset
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.schema import EvaluationAttempt


def _sha256(path: Path) -> str:
    """Hash a frozen input."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(result_path: Path, dataset_path: Path, protocol_path: Path) -> dict:
    """Check provenance, saved output contracts, and fixed group counts."""
    result = json.loads(result_path.read_text(encoding="utf-8"))
    dataset = AIHeldoutDataset.model_validate_json(dataset_path.read_bytes())
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if set(result) != {
        "kind",
        "claim_scope",
        "protocol_sha256",
        "dataset_sha256",
        "baseline_revision",
        "candidate_revision",
        "model_sha256",
        "restarts_after_case",
        "summaries",
        "results",
    }:
        raise ValueError("result contains unexpected root keys")
    if result["kind"] != "ai_authored_safety_postfreeze_pair_result_v1":
        raise ValueError("unexpected result kind")
    if result["protocol_sha256"] != _sha256(protocol_path):
        raise ValueError("protocol digest differs")
    if result["dataset_sha256"] != _sha256(dataset_path):
        raise ValueError("dataset digest differs")
    if result["dataset_sha256"] != protocol["dataset_sha256"]:
        raise ValueError("dataset differs from pre-exposure protocol")
    for key in ("baseline_revision", "candidate_revision", "model_sha256"):
        if result[key] != protocol[key]:
            raise ValueError(f"{key} differs from protocol")
    expected_restarts = list(
        range(protocol["restart_every_cases"], 16, protocol["restart_every_cases"])
    )
    if result["restarts_after_case"] != expected_restarts:
        raise ValueError("restart positions differ")
    cases = dataset.cases
    if [case.id for case in cases] != [f"nlu-safety-postfreeze-pf{i:02}" for i in range(1, 17)]:
        raise ValueError("dataset IDs or order differ")
    summaries: dict[str, dict] = {}
    for role in ("baseline", "candidate"):
        rows = result["results"][role]
        if [row["case_id"] for row in rows] != [case.id for case in cases]:
            raise ValueError(f"{role} result IDs or order differ")
        for case, row in zip(cases, rows, strict=True):
            if set(row) != {
                "case_id",
                "model_request_count",
                "attempts",
                "conversation_state",
                "workflow_status",
                "safety_status",
                "error_type",
            }:
                raise ValueError("result contains unexpected case keys")
            if row["model_request_count"] != len(row["attempts"]):
                raise ValueError("request count differs from attempts")
            if not 0 <= row["model_request_count"] <= 2:
                raise ValueError("unexpected retry count")
            if (
                row["model_request_count"] == 0
                and row["conversation_state"] != "safety_action_required"
            ):
                raise ValueError("zero-request case did not enter the safety route")
            for attempt in row["attempts"]:
                if set(attempt) != {"contract_valid", "latency_ms", "output", "error_type"}:
                    raise ValueError("result contains unexpected attempt keys")
                validated = EvaluationAttempt.model_validate(attempt)
                if validated.output is not None:
                    output = validated.output
                    EVALUATION_CONTRACTS[case.scenario_key].validate_prediction(
                        intent=output.intent,
                        fields=output.fields,
                        user_action=output.user_action,
                        change_field=output.change_field,
                        conversation_state=case.conversation_state,
                        current_fields=case.current_fields,
                        offered_alternative_times=case.offered_alternative_times,
                    )
        positive, negative = rows[:8], rows[8:]
        summary = {}
        for key, group, safety_key in (
            ("safety_positive", positive, "entered_safety_state"),
            ("safety_negative", negative, "incorrectly_entered_safety_state"),
        ):
            summary[key] = {
                "denominator": len(group),
                safety_key: sum(
                    row["conversation_state"] == "safety_action_required" for row in group
                ),
                "model_requests": sum(row["model_request_count"] for row in group),
                "zero_request_bypasses": sum(row["model_request_count"] == 0 for row in group),
                "graph_errors": sum(row["error_type"] is not None for row in group),
            }
        if summary != result["summaries"][role]:
            raise ValueError(f"{role} summary differs from case results")
        summaries[role] = summary
    return summaries


def main() -> None:
    """Verify a result without contacting a model."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.result, args.dataset, args.protocol), ensure_ascii=False))


if __name__ == "__main__":
    main()
