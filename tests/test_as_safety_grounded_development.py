"""Keep the development candidate separate from the frozen TX set."""

from pathlib import Path

import pytest

from scripts.probe_as_safety_grounded_attribution import validate_grounded
from scripts.run_as_safety_grounded_development import load_exposed_cases, load_policy
from scripts.verify_as_safety_grounded_development import verify_candidate_decision


def test_development_loader_uses_only_prior_exposed_cases():
    cases = load_exposed_cases()
    assert [case["id"] for case in cases] == [
        *(f"RE{index:02}" for index in range(1, 17)),
        *(f"V{index:02}" for index in range(1, 17)),
    ]
    assert all(case["id"][:2] != "TX" for case in cases)


def test_request_policy_explicitly_disables_retries():
    settings = load_policy(
        Path("evals/structured_nlu/data/ai_heldout/as-safety-grounded-development-request.v1.json")
    )
    assert settings.temperature == 0
    assert settings.max_tokens == 180


def test_independent_span_audit_rejects_changed_relation_or_evidence():
    message = "수리할 제습기 화면이 꺼집니다. 옆 선풍기에서 연기가 났습니다."
    raw = (
        '{"product_index":1,"hazard_index":2,"product_anchor":"제습기",'
        '"hazard_owner_anchor":"선풍기","target_relation":"other",'
        '"event_status":"observed"}'
    )
    decision = validate_grounded(raw, message)
    assert verify_candidate_decision(decision, message) == "collecting_service_request"
    changed_relation = {**decision, "anchor_relation": "current"}
    with pytest.raises(ValueError, match="anchor relation"):
        verify_candidate_decision(changed_relation, message)
    changed_span = {**decision, "owner_end": decision["owner_start"]}
    with pytest.raises(ValueError, match="hazard owner span"):
        verify_candidate_decision(changed_span, message)
