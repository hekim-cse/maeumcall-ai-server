"""Contract tests for the owner-oracle dual-question development candidate."""

from __future__ import annotations

import json

import pytest

from experiments.as_safety_dual_query_v1.contract import (
    ARMS,
    combine_decisions,
    decision_messages,
    decision_schema,
    validate_decision,
)
from experiments.as_safety_v2.json_contract import ValidationError


def _case() -> tuple[dict, dict]:
    case = {
        "user_message": "전기포트의 전원선에서 연기가 났습니다.",
        "target": {"clause_index": 1, "quote": "전기포트"},
        "expected_route": "safety_action_required",
    }
    event = {
        "event_span": {"clause_index": 1, "quote": "연기가 났습니다"},
        "hazard_owner_span": {"clause_index": 1, "quote": "전기포트의 전원선"},
        "occurrence": "observed",
        "owner_to_target": "current",
    }
    return case, event


def test_questions_are_independent_and_never_send_gold_relation_or_route() -> None:
    case, gold = _case()
    assert ARMS == ("current", "distinct")
    first = decision_messages(case, gold, "current")
    second = decision_messages(case, gold, "distinct")
    assert first[1] == second[1]
    payload = json.loads(first[1]["content"])
    assert set(payload) == {
        "user_message",
        "target",
        "event_span",
        "hazard_owner_span",
        "occurrence",
    }
    assert "owner_to_target" not in first[1]["content"]
    assert "safety_action_required" not in first[1]["content"]
    assert first[0]["content"] != second[0]["content"]
    assert "별개의 물건" in second[0]["content"]


def test_schema_and_parser_accept_only_one_valid_decision() -> None:
    schema = decision_schema()
    assert schema["required"] == ["decision"]
    assert schema["additionalProperties"] is False
    for answer in ("yes", "no", "unknown"):
        assert validate_decision(json.dumps({"decision": answer})) == answer
    for raw in (
        '{"decision":"yes","decision":"no"}',
        '{"decision":"yes","reason":"guessed"}',
        '{"decision":"current"}',
        '{"decision":true}',
        "not json",
    ):
        with pytest.raises(ValidationError):
            validate_decision(raw)


@pytest.mark.parametrize(
    ("current", "distinct", "expected"),
    [
        ("yes", "no", "current"),
        ("no", "yes", "other"),
        ("yes", "yes", "unknown"),
        ("no", "no", "unknown"),
        ("unknown", "no", "unknown"),
        ("no", "unknown", "unknown"),
        ("unknown", "unknown", "unknown"),
        (None, "yes", "unknown"),
        ("yes", None, "unknown"),
    ],
)
def test_join_abstains_without_complementary_evidence(current, distinct, expected) -> None:
    assert combine_decisions(current, distinct) == expected


def test_invalid_inputs_fail_before_model_request_or_join() -> None:
    case, gold = _case()
    with pytest.raises(ValueError, match="invalid question arm"):
        decision_messages(case, gold, "other")
    with pytest.raises(ValueError, match="owner-oracle"):
        decision_messages(case, {**gold, "hazard_owner_span": None}, "current")
    with pytest.raises(ValueError, match="owner-oracle"):
        decision_messages(case, {**gold, "occurrence": "nonoccurring"}, "current")
    with pytest.raises(ValueError, match="invalid decision"):
        combine_decisions("maybe", "no")
