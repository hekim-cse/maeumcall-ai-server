"""Check the coverage denominator and numbered evidence contract."""

import json

import pytest

from experiments.as_safety_atomic_edges_v18 import run, selection
from experiments.as_safety_v2.json_contract import ValidationError


def test_coverage_and_conditional_selection_are_independent():
    _, requests = run.calls()
    pair = requests["PC01-P014-forward"][0]
    gold = {"evidence_clause_index": 2, "relation_status": "supported"}
    assert run.coverage() == {
        name: True for name in ("PC01-P014", "PC01-P016", "NC01-P020", "NC01-P002")
    }

    raw = '{"source_evidence":2,"exclusion_evidence":null,"uncertainty_evidence":null}'
    result = selection.validate_response(raw, pair)
    assert selection.score(pair, gold, result)["gold_evidence_selected_if_offered"] is True
    assert selection.score(pair, gold, None)["gold_evidence_selected_if_offered"] is False
    uncovered = selection.score(pair, {**gold, "evidence_clause_index": 99}, result)
    assert uncovered["gold_candidate_offered"] is False
    assert uncovered["gold_evidence_selected_if_offered"] is None


def test_numbered_responses_reject_unoffered_ids_booleans_and_conflicts():
    _, requests = run.calls()
    pair = requests["PC01-P014-forward"][0]
    for bad in (99, True, "2"):
        raw = json.dumps(
            {"source_evidence": bad, "exclusion_evidence": None, "uncertainty_evidence": None}
        )
        with pytest.raises(ValidationError, match="evidence_candidate_not_offered"):
            selection.validate_response(raw, pair)
    with pytest.raises(ValidationError, match="conflicting_source_evidence"):
        selection.validate_response(
            '{"source_evidence":2,"exclusion_evidence":1,"uncertainty_evidence":null}', pair
        )


def test_requests_hold_schema_and_candidates_fixed_when_questions_reverse():
    _, requests = run.calls()
    for case_id, candidate_id in run.v12.ORDER:
        name = f"{case_id}-{candidate_id}"
        forward = json.loads(requests[f"{name}-forward"][3])
        reverse = json.loads(requests[f"{name}-reverse"][3])
        left = forward["messages"][1]["content"].splitlines()
        right = reverse["messages"][1]["content"].splitlines()
        assert left[-4:-1] == right[-4:-1][::-1]
        right[-4:-1] = reversed(right[-4:-1])
        reverse["messages"][1]["content"] = "\n".join(right)
        assert forward == reverse
