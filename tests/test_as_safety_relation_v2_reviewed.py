"""Guard the owner-reviewed, still-unexposed V01–V16 input boundary."""

import json
from pathlib import Path

from scripts.probe_as_safety_clause_index import split_clauses
from scripts.probe_as_safety_entailment_v2 import route_entailment, validate_entailment
from scripts.probe_as_safety_relation import route_relation, validate_relation


def test_reviewed_v_cases_have_consistent_route_labels():
    path = Path("evals/structured_nlu/data/ai_heldout/as-safety-relation-v2-fresh-reviewed.v1.json")
    payload = json.loads(path.read_text())
    assert payload["provenance"] == "ai_authored"
    assert payload["review_status"] == "owner_approved_for_exploration"
    assert payload["model_exposure_at_freeze"] == "none"
    cases = payload["cases"]
    assert [case["id"] for case in cases] == [f"V{index:02}" for index in range(1, 17)]
    for case in cases:
        count = len(split_clauses(case["user_message"]))
        assert count == 2
        relation = validate_relation(json.dumps(case["expected_relation"]), count)
        entailment = validate_entailment(json.dumps(case["expected_entailment"]), count)
        assert route_relation(relation) == case["expected_route"]
        assert route_entailment(entailment) == case["expected_route"]
