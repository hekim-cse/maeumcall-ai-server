"""Independently recount a frozen A/S safety confirmation graph comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

from evals.structured_nlu.ai_heldout import AIHeldoutDataset
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.schema import EvaluationAttempt


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(result_path: Path, dataset_path: Path, goals_path: Path, protocol_path: Path) -> dict:
    """Validate fixed inputs, bounded output, legal states, and all reported counts."""
    result = json.loads(result_path.read_text(encoding="utf-8"))
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    goals = json.loads(goals_path.read_text(encoding="utf-8"))
    dataset = AIHeldoutDataset.model_validate_json(dataset_path.read_bytes())
    version = result.get("kind")
    if version not in {
        "ai_authored_safety_confirmation_pair_result_v1",
        "ai_authored_safety_confirmation_pair_result_v2",
    }:
        raise ValueError("unexpected result kind")
    expected_keys = {
        "kind",
        "claim_scope",
        "protocol_sha256",
        "dataset_sha256",
        "graph_goals_sha256",
        "baseline_revision",
        "candidate_revision",
        "model_sha256",
        "restarts_after_case",
        "summaries",
        "results",
    }
    if version.endswith("v2"):
        expected_keys.add("execution_order")
    if set(result) != expected_keys:
        raise ValueError("unexpected result keys")
    expected_scope = (
        "same_32_case_replay_after_v1_exposure_for_order_provenance"
        if version.endswith("v2")
        else "single_owner_reviewed_ai_authored_32_case_as_safety_stress"
    )
    if result["claim_scope"] != expected_scope:
        raise ValueError("unexpected claim scope")
    if protocol.get("kind") != f"ai_authored_safety_confirmation_pair_protocol_{version[-2:]}":
        raise ValueError("protocol and result versions differ")
    if result["protocol_sha256"] != _sha256(protocol_path):
        raise ValueError("protocol hash differs")
    for path, key in (
        (dataset_path, "dataset_sha256"),
        (goals_path, "graph_goals_sha256"),
    ):
        if result[key] != _sha256(path) or protocol[key] != result[key]:
            raise ValueError(f"{key} differs from frozen input")
    if goals["dataset_sha256"] != result["dataset_sha256"]:
        raise ValueError("goals dataset binding differs")
    for key in ("baseline_revision", "candidate_revision", "model_sha256"):
        if result[key] != protocol[key]:
            raise ValueError(f"{key} differs from protocol")
    expected_restarts = list(
        range(protocol["restart_every_cases"], 32, protocol["restart_every_cases"])
    )
    if result["restarts_after_case"] != expected_restarts:
        raise ValueError("restart positions differ")
    cases = dataset.cases
    expected_ids = [f"nlu-safety-confirmation-cf{number:02}" for number in range(1, 33)]
    if [case.id for case in cases] != expected_ids:
        raise ValueError("dataset IDs or order differ")
    if version.endswith("v2"):
        expected_order = [
            {"case_id": case_id, "role": role}
            for index, case_id in enumerate(expected_ids)
            for role in (("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline"))
        ]
        if result["execution_order"] != expected_order:
            raise ValueError("execution order differs from alternating protocol")
    if (
        set(goals) != {"kind", "dataset_sha256", "goals"}
        or goals["kind"] != "ai_authored_safety_confirmation_goals_v1"
    ):
        raise ValueError("unexpected graph goals")
    if [goal["case_id"] for goal in goals["goals"]] != expected_ids:
        raise ValueError("graph goal order differs")
    expected_states = (
        ["safety_action_required"] * 12
        + ["confirming_safety_status"] * 8
        + ["collecting_service_request"] * 12
    )
    if [goal["expected_state"] for goal in goals["goals"]] != expected_states:
        raise ValueError("graph goals differ from reviewed groups")
    if set(result["results"]) != {"baseline", "candidate"} or set(result["summaries"]) != {
        "baseline",
        "candidate",
    }:
        raise ValueError("unexpected result roles")
    summaries = {}
    for role in ("baseline", "candidate"):
        rows = result["results"][role]
        if [row["case_id"] for row in rows] != expected_ids:
            raise ValueError(f"{role} result order differs")
        for case, row in zip(cases, rows, strict=True):
            _verify_row(case, row, role)
        grouped = {
            "confirmed_hazard": rows[:12],
            "ambiguous_hazard": rows[12:20],
            "no_current_hazard": rows[20:],
        }
        summary = {}
        for group_name, group in grouped.items():
            summary[group_name] = {
                "denominator": len(group),
                "direct_safety": sum(
                    x["conversation_state"] == "safety_action_required" for x in group
                ),
                "safety_confirmation": sum(
                    x["conversation_state"] == "confirming_safety_status" for x in group
                ),
                "normal_collection": sum(
                    x["conversation_state"] == "collecting_service_request" for x in group
                ),
                "extraction_requests": sum(x["model_request_count"] for x in group),
                "focus_requests": sum(x["focus_request_count"] for x in group),
                "graph_errors": sum(x["error_type"] is not None for x in group),
                "median_graph_latency_ms": round(
                    statistics.median(x["graph_latency_ms"] for x in group), 3
                ),
            }
        if summary != result["summaries"][role]:
            raise ValueError(f"{role} summary differs from cases")
        summaries[role] = summary
    return summaries


def _verify_row(case, row: dict, role: str) -> None:
    if set(row) != {
        "case_id",
        "model_request_count",
        "attempts",
        "conversation_state",
        "workflow_status",
        "safety_status",
        "error_type",
        "focus_request_count",
        "focus_attempts",
        "graph_latency_ms",
    }:
        raise ValueError("unexpected case keys or raw model text")
    if (
        row["model_request_count"] != len(row["attempts"])
        or not 0 <= row["model_request_count"] <= 2
    ):
        raise ValueError("invalid extraction request count")
    if (
        row["focus_request_count"] != len(row["focus_attempts"])
        or not 0 <= row["focus_request_count"] <= 2
    ):
        raise ValueError("invalid focused request count")
    if role == "baseline" and row["focus_request_count"]:
        raise ValueError("baseline cannot use focused model")
    if not isinstance(row["graph_latency_ms"], (int, float)) or row["graph_latency_ms"] < 0:
        raise ValueError("invalid graph latency")
    for attempt in row["focus_attempts"]:
        if set(attempt) != {"decision", "error_type", "latency_ms"}:
            raise ValueError("unexpected focused attempt keys")
        if attempt["decision"] is not None and not isinstance(attempt["decision"], bool):
            raise ValueError("invalid focused decision")
        if attempt["error_type"] is None and attempt["decision"] is None:
            raise ValueError("missing focused attempt outcome")
        if attempt["error_type"] is not None and attempt["decision"] is not None:
            raise ValueError("contradictory focused attempt")
        if not isinstance(attempt["latency_ms"], (int, float)) or attempt["latency_ms"] < 0:
            raise ValueError("invalid focused latency")
    if row["focus_attempts"] and any(x["decision"] is not None for x in row["focus_attempts"][:-1]):
        raise ValueError("focused model continued after valid decision")
    for attempt in row["attempts"]:
        if set(attempt) != {"contract_valid", "latency_ms", "output", "error_type"}:
            raise ValueError("unexpected extraction attempt keys")
        validated = EvaluationAttempt.model_validate(attempt)
        if validated.contract_valid != (validated.output is not None):
            raise ValueError("extraction validity differs from output")
        if (validated.error_type is None) != validated.contract_valid:
            raise ValueError("extraction error differs from validity")
        if validated.output is not None:
            EVALUATION_CONTRACTS[case.scenario_key].validate_prediction(
                intent=validated.output.intent,
                fields=validated.output.fields,
                user_action=validated.output.user_action,
                change_field=validated.output.change_field,
                conversation_state=case.conversation_state,
                current_fields=case.current_fields,
                offered_alternative_times=case.offered_alternative_times,
            )
    if row["attempts"] and (
        any(x["contract_valid"] for x in row["attempts"][:-1])
        or (row["error_type"] is None and not row["attempts"][-1]["contract_valid"])
    ):
        raise ValueError("extraction retry order differs")
    if row["error_type"] is None:
        state = row["conversation_state"]
        if row["attempts"] and row["attempts"][-1]["output"] is not None:
            extracted_safety = row["attempts"][-1]["output"]["fields"]["safety_status"]
            if extracted_safety == "safety_issue" and (
                state != "safety_action_required" or row["safety_status"] != "safety_issue"
            ):
                raise ValueError("extracted safety issue did not reach direct safety state")
        if state == "safety_action_required":
            if row["workflow_status"] != "blocked" or row["safety_status"] != "safety_issue":
                raise ValueError("direct safety state differs")
        elif state == "confirming_safety_status":
            if (
                role != "candidate"
                or row["focus_request_count"] == 0
                or row["model_request_count"]
                or row["focus_attempts"][-1]["decision"] is False
            ):
                raise ValueError("confirmation provenance differs")
            if row["workflow_status"] != "blocked" or row["safety_status"] is not None:
                raise ValueError("confirmation state differs")
        elif state == "collecting_service_request":
            if not row["attempts"] or row["workflow_status"] != "in_progress":
                raise ValueError("normal collection state differs")
            if row["safety_status"] not in (None, "no_safety_issue"):
                raise ValueError("normal safety status differs")
        else:
            raise ValueError("unexpected graph state")
        if (
            row["focus_attempts"]
            and row["focus_attempts"][-1]["decision"] is True
            and state != "confirming_safety_status"
        ):
            raise ValueError("positive focus decision did not ask for confirmation")
    elif row["error_type"] == "AIResponseValidationError":
        if len(row["attempts"]) != 2 or any(x["contract_valid"] for x in row["attempts"]):
            raise ValueError("extraction retry exhaustion differs")
        if any(
            row[key] is not None
            for key in ("conversation_state", "workflow_status", "safety_status")
        ):
            raise ValueError("failed graph contains state")
    else:
        raise ValueError("unexpected graph error")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--goals", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(verify(args.result, args.dataset, args.goals, args.protocol), ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
