"""Cover the evidence-to-status boundary before any model calls."""

import json
from pathlib import Path

import pytest
from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v10.probe import cases
from experiments.as_safety_atomic_edges_v12.pair_contract import fixed_pair
from experiments.as_safety_atomic_edges_v17 import run
from experiments.as_safety_atomic_edges_v17.evidence_contract import messages, validate_response
from experiments.as_safety_v2.json_contract import ValidationError

REVIEWED = (
    Path(__file__).resolve().parents[1]
    / "evals/structured_nlu/data/ai_heldout/as-safety-eb-pair-v12-reviewed.json"
)


@pytest.fixture(scope="module")
def pairs():
    kiwi = Kiwi()
    source = cases()
    return {
        f"{case_id}-{candidate_id}": fixed_pair(source[case_id], candidate_id, kiwi)
        for case_id, candidate_id in [
            ("PC01", "P014"),
            ("PC01", "P016"),
            ("NC01", "P020"),
            ("NC01", "P002"),
        ]
    }


def response(*, source=None, exclusion=None, uncertainty=None):
    return json.dumps(
        {
            "source_evidence": source,
            "exclusion_evidence": exclusion,
            "uncertainty_evidence": uncertainty,
        }
    )


def test_offline_fixtures_reproduce_reviewed_status_and_clause(pairs):
    outputs = {
        "PC01-P014": response(
            source={"clause_index": 2, "quote": "선풍기 모터에서 연기가 났습니다"}
        ),
        "PC01-P016": response(
            exclusion={"clause_index": 2, "quote": "선풍기 모터에서 연기가 났습니다"}
        ),
        "NC01-P020": response(
            exclusion={"clause_index": 2, "quote": "타는 냄새가 납니다"},
            uncertainty={"clause_index": 3, "quote": "냄새가 어디서 나는지는 확인하지 못했습니다"},
        ),
        "NC01-P002": response(
            uncertainty={"clause_index": 3, "quote": "냄새가 어디서 나는지는 확인하지 못했습니다"}
        ),
    }
    for gold in json.loads(REVIEWED.read_text(encoding="utf-8"))["cases"]:
        call = gold["call"]
        result = validate_response(outputs[call], pairs[call])
        assert result["relation_status"] == gold["relation_status"]
        assert result["evidence_clause_index"] == gold["evidence_clause_index"]


def test_missing_evidence_abstains(pairs):
    result = validate_response(response(), pairs["PC01-P014"])
    assert result["relation_status"] == "insufficient"
    assert result["evidence_clause_index"] is None


def test_unanchored_or_conflicting_evidence_is_rejected(pairs):
    pair = pairs["PC01-P014"]
    with pytest.raises(ValidationError, match="quote_unanchored"):
        validate_response(response(source={"clause_index": 1, "quote": "연기가 났습니다"}), pair)
    span = {"clause_index": 2, "quote": "선풍기 모터에서 연기가 났습니다"}
    with pytest.raises(ValidationError, match="conflicting_source_evidence"):
        validate_response(response(source=span, exclusion=span), pair)


def test_reverse_only_changes_the_order_of_the_three_questions(pairs):
    pair = pairs["PC01-P014"]
    forward = messages(pair)
    reverse = messages(pair, reverse_questions=True)
    assert forward[0] == reverse[0]
    left = forward[1]["content"].splitlines()
    right = reverse[1]["content"].splitlines()
    assert left[:-4] == right[:-4]
    assert left[-4:-1] == right[-4:-1][::-1]
    assert left[-1] == right[-1]


def test_frozen_request_inputs_are_interleaved_and_only_reverse_questions():
    _, calls = run.calls()
    assert list(calls) == [
        f"{case_id}-{candidate_id}-{order}"
        for case_id, candidate_id in run.v12.ORDER
        for order in ("forward", "reverse")
    ]
    for case_id, candidate_id in run.v12.ORDER:
        name = f"{case_id}-{candidate_id}"
        forward = json.loads(calls[f"{name}-forward"][3])
        reverse = json.loads(calls[f"{name}-reverse"][3])
        left = forward["messages"][1]["content"].splitlines()
        right = reverse["messages"][1]["content"].splitlines()
        assert left[-4:-1] == right[-4:-1][::-1]
        right[-4:-1] = reversed(right[-4:-1])
        reverse["messages"][1]["content"] = "\n".join(right)
        assert forward == reverse
