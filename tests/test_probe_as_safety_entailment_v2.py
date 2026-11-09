"""Guard the focused hazard-entailment contract and routing."""

import json

import pytest

from scripts.probe_as_safety_entailment_v2 import route_entailment, validate_entailment


@pytest.mark.parametrize(
    ("claim", "reason", "route"),
    [
        ("entailed", "same_product_observed", "safety_action_required"),
        ("contradicted", "other_source", "collecting_service_request"),
        ("contradicted", "nonoccurring", "collecting_service_request"),
        ("uncertain", "uncertain", "confirming_safety_status"),
    ],
)
def test_coherent_decisions_route_as_declared(claim, reason, route):
    decision = validate_entailment(
        json.dumps({"hazard_index": 2, "claim": claim, "reason": reason}), 2
    )
    assert route_entailment(decision) == route


@pytest.mark.parametrize(
    "decision",
    [
        {"hazard_index": 3, "claim": "entailed", "reason": "same_product_observed"},
        {"hazard_index": 1, "claim": "entailed", "reason": "other_source"},
        {"hazard_index": None, "claim": "uncertain", "reason": "uncertain"},
        {"hazard_index": True, "claim": "contradicted", "reason": "other_source"},
    ],
)
def test_invalid_or_unsupported_claim_is_rejected(decision):
    with pytest.raises(ValueError):
        validate_entailment(json.dumps(decision), 2)
