"""Check the frozen RE/V adapter and its independent decision verifier."""

import json
from pathlib import Path

import pytest

from scripts.run_as_safety_typed_relation_development import load_exposed_cases, load_policy
from scripts.verify_as_safety_typed_relation_development import verify_candidate_decision

DATA = Path("evals/structured_nlu/data/ai_heldout")
POLICY = DATA / "as-safety-grounded-development-request.v1.json"
MESSAGE = "제 공기청정기에서 연기가 났습니다. 전원을 껐습니다."


def decision(**changes):
    result = {
        "product_index": 1,
        "event_index": 1,
        "source_index": 1,
        "occurrence_index": 1,
        "source_relation": "current_product",
        "event_status": "observed",
    }
    result.update(changes)
    return result


def test_runner_reuses_frozen_policy_and_only_reviewed_re_v_cases():
    policy = load_policy(POLICY)
    assert policy.max_tokens == 180
    assert policy.temperature == 0
    assert [case["id"] for case in load_exposed_cases()] == [
        *(f"RE{i:02}" for i in range(1, 17)),
        *(f"V{i:02}" for i in range(1, 17)),
    ]


@pytest.mark.parametrize(
    ("changes", "route"),
    [
        ({}, "safety_action_required"),
        ({"source_relation": "current_part"}, "safety_action_required"),
        ({"source_relation": "other_product"}, "collecting_service_request"),
        ({"source_relation": "location_only"}, "confirming_safety_status"),
        ({"source_relation": "alternative_unknown"}, "confirming_safety_status"),
        ({"event_status": "uncertain"}, "confirming_safety_status"),
        ({"event_status": "nonoccurring"}, "collecting_service_request"),
    ],
)
def test_verifier_recomputes_routes(changes, route):
    assert verify_candidate_decision(decision(**changes), MESSAGE) == route


def test_verifier_allows_separate_source_and_occurrence_evidence():
    assert (
        verify_candidate_decision(
            decision(source_index=2, occurrence_index=1, source_relation="alternative_unknown"),
            MESSAGE,
        )
        == "confirming_safety_status"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"event_index": None},
        {"occurrence_index": None},
        {"product_index": None},
        {"source_index": None},
        {"source_index": 3},
        {"event_index": True},
        {"event_status": "none"},
    ],
)
def test_verifier_rejects_inconsistent_or_unbounded_evidence(changes):
    with pytest.raises(ValueError):
        verify_candidate_decision(decision(**changes), MESSAGE)


def test_verifier_accepts_empty_event_only_with_empty_edges():
    empty = decision(
        product_index=None,
        event_index=None,
        source_index=None,
        occurrence_index=None,
        source_relation="none",
        event_status="none",
    )
    assert verify_candidate_decision(empty, MESSAGE) == "collecting_service_request"
    with pytest.raises(ValueError):
        verify_candidate_decision({**empty, "source_index": 1}, MESSAGE)


def test_policy_cannot_silently_change_request_settings(tmp_path):
    changed = json.loads(POLICY.read_text(encoding="utf-8"))
    changed["temperature"] = 1
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="request policy differs"):
        load_policy(path)
