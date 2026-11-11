"""Audit forced A/S safety routing before structured model extraction.

This is an exposed-case diagnostic of the existing guard, not a model score or
an end-to-end workflow evaluation. A nonmatch leaves the model path unknown.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from services.flow.service_workflow.safety import has_explicit_safety_issue

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
SOURCES = (
    (DATA / "as-safety-relation-fresh-reviewed.v1.json", "RE"),
    (DATA / "as-safety-relation-v2-fresh-reviewed.v1.json", "V"),
)


def audit() -> dict:
    """Count only outcomes forced by the pre-model guard on reviewed cases."""
    cases = []
    for path, prefix in SOURCES:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("provenance") != "ai_authored"
            or payload.get("review_status") != "owner_approved_for_exploration"
            or len(payload.get("cases", [])) != 16
            or [case["id"] for case in payload["cases"]]
            != [f"{prefix}{i:02}" for i in range(1, 17)]
        ):
            raise ValueError("reviewed A/S source differs")
        cases.extend(payload["cases"])
    forced = [case for case in cases if has_explicit_safety_issue(case["user_message"])]
    expected_safety = [
        case for case in forced if case["expected_route"] == "safety_action_required"
    ]
    false_direct = [case for case in forced if case["expected_route"] != "safety_action_required"]
    groups = Counter(
        (case["expected_relation"]["target_relation"], case["expected_relation"]["event_status"])
        for case in cases
    )
    other_observed = [
        case
        for case in cases
        if case["expected_relation"]["target_relation"] == "other"
        and case["expected_relation"]["event_status"] == "observed"
    ]
    current_observed = [
        case
        for case in cases
        if case["expected_relation"]["target_relation"] == "current"
        and case["expected_relation"]["event_status"] == "observed"
    ]
    return {
        "claim_scope": "exposed_ai_authored_pre_model_guard_diagnostic_only",
        "cases": len(cases),
        "forced_safety": len(forced),
        "forced_safety_ids": [case["id"] for case in forced],
        "forced_safety_expected": len(expected_safety),
        "forced_safety_false_direct": len(false_direct),
        "false_direct_ids": [case["id"] for case in false_direct],
        "current_observed_total": len(current_observed),
        "current_observed_forced": sum(case in forced for case in current_observed),
        "other_observed_total": len(other_observed),
        "other_observed_forced": sum(case in forced for case in other_observed),
        "gold_groups": {
            f"{relation}:{status}": count for (relation, status), count in sorted(groups.items())
        },
        "unmatched_route_unmeasured": True,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
