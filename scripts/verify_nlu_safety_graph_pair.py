"""Independently verify the frozen A/S graph pair result and its denominators."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(result_path: Path, dataset_path: Path, protocol_path: Path) -> dict:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if result["kind"] != "ai_authored_safety_graph_pair_result_v1":
        raise ValueError("unexpected result kind")
    if result["protocol_sha256"] != _sha256(protocol_path):
        raise ValueError("protocol digest differs")
    if result["dataset_sha256"] != _sha256(dataset_path):
        raise ValueError("dataset digest differs")
    for key in ("baseline_revision", "candidate_revision", "model_sha256"):
        if result[key] != protocol[key]:
            raise ValueError(f"{key} differs")
    if result["restarts_after_case"] != [5, 10, 15]:
        raise ValueError("restart positions differ")
    ids = [case["id"] for case in dataset["cases"]]
    if ids != [f"nlu-safety-contract-sc{index:02}" for index in range(1, 21)]:
        raise ValueError("dataset IDs or order differ")
    summaries = {}
    for role in ("baseline", "candidate"):
        rows = result["results"][role]
        if [row["case_id"] for row in rows] != ids:
            raise ValueError(f"{role} result IDs or order differ")
        for row in rows:
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
                raise ValueError("model request count differs from attempts")
            if not 0 <= row["model_request_count"] <= 2:
                raise ValueError("unexpected retry count")
            if (
                row["model_request_count"] == 0
                and row["conversation_state"] != "safety_action_required"
            ):
                raise ValueError("zero-request case did not take safety bypass")
            for attempt in row["attempts"]:
                if set(attempt) != {"contract_valid", "latency_ms", "output", "error_type"}:
                    raise ValueError("result contains unexpected attempt keys")
                if attempt["contract_valid"] != (attempt["output"] is not None):
                    raise ValueError("contract flag differs from normalized output")
        positives, negatives, scope = rows[:8], rows[8:16], rows[16:]
        summary = {
            "safety_positive": {
                "denominator": len(positives),
                "entered_safety_state": sum(
                    row["conversation_state"] == "safety_action_required" for row in positives
                ),
                "model_requests": sum(row["model_request_count"] for row in positives),
            },
            "safety_negative": {
                "denominator": len(negatives),
                "incorrectly_entered_safety_state": sum(
                    row["conversation_state"] == "safety_action_required" for row in negatives
                ),
                "model_requests": sum(row["model_request_count"] for row in negatives),
            },
            "out_of_scope": {
                "denominator": len(scope),
                "contract_pass": sum(
                    bool(row["attempts"]) and row["attempts"][-1]["contract_valid"] for row in scope
                ),
                "unknown_action": sum(
                    bool(row["attempts"])
                    and row["attempts"][-1]["output"] is not None
                    and row["attempts"][-1]["output"]["user_action"] == "unknown"
                    for row in scope
                ),
                "model_requests": sum(row["model_request_count"] for row in scope),
            },
        }
        if summary != result["summaries"][role]:
            raise ValueError(f"{role} summary differs from case results")
        summaries[role] = summary
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.result, args.dataset, args.protocol), ensure_ascii=False))


if __name__ == "__main__":
    main()
