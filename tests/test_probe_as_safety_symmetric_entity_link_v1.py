"""Check the finite symmetric entity-link contract without model requests."""

from __future__ import annotations

import itertools
import json

import pytest

from scripts.probe_as_safety_symmetric_entity_link_v1 import (
    symmetric_entity_link_messages,
    symmetric_entity_link_schema,
    validate_symmetric_entity_link,
)

MESSAGE = "수리 맡길 노트북이 켜지지 않습니다. 친구 태블릿의 충전기에서 연기가 났습니다."
ANCHORS = {
    "product_index": 1,
    "target_mention": "노트북",
    "owner_clause_index": 2,
    "owner_mention": "친구 태블릿의 충전기",
}


def test_messages_preserve_original_text_without_gold_or_safety_decisions():
    messages = symmetric_entity_link_messages(MESSAGE, **ANCHORS)
    assert [message["role"] for message in messages] == ["system", "user"]
    prompt = messages[1]["content"]
    assert f"원문 전체: {MESSAGE}" in prompt
    assert "1. 수리 맡길 노트북이 켜지지 않습니다." in prompt
    assert "2. 친구 태블릿의 충전기에서 연기가 났습니다." in prompt
    assert "구절 A 근거: 1." in prompt and "구절 A: 노트북\n" in prompt
    assert "구절 B 근거: 2." in prompt and "구절 B: 친구 태블릿의 충전기\n" in prompt
    assert "same_or_part:" in prompt and "distinct_item:" in prompt
    assert "expected_relation" not in prompt
    assert "event_status" not in prompt
    assert "accepted_link_kinds" not in prompt
    assert "source_relation" not in prompt


def test_schema_contains_only_two_finite_model_answers():
    schema = symmetric_entity_link_schema()
    assert schema == {
        "type": "object",
        "properties": {
            "same_or_part": {"enum": ["no", "uncertain", "yes"]},
            "distinct_item": {"enum": ["no", "uncertain", "yes"]},
        },
        "required": ["same_or_part", "distinct_item"],
        "additionalProperties": False,
    }


@pytest.mark.parametrize("same,distinct", itertools.product(["yes", "no", "uncertain"], repeat=2))
def test_only_opposing_certain_answers_produce_a_confirmed_link(same, distinct):
    raw = json.dumps({"same_or_part": same, "distinct_item": distinct})
    expected = {
        ("yes", "no"): "same_or_part",
        ("no", "yes"): "distinct_item",
    }.get((same, distinct), "unresolved")
    assert validate_symmetric_entity_link(raw) == {
        "same_or_part_answer": same,
        "distinct_item_answer": distinct,
        "entity_link": expected,
    }


@pytest.mark.parametrize(
    "raw",
    [
        '{"same_or_part":"yes","same_or_part":"no","distinct_item":"no"}',
        '{"same_or_part":"yes","distinct_item":"no","reason":"same model"}',
        '{"same_or_part":"yes"}',
        '{"same_or_part":true,"distinct_item":"no"}',
        '{"same_or_part":null,"distinct_item":"no"}',
        '{"same_or_part":"current","distinct_item":"no"}',
        '{"same_or_part":"yes","distinct_item":NaN}',
        "[]",
        "{",
    ],
)
def test_malformed_or_leaky_output_is_rejected(raw):
    with pytest.raises((ValueError, json.JSONDecodeError)):
        validate_symmetric_entity_link(raw)


def test_nontext_response_is_rejected():
    with pytest.raises(TypeError):
        validate_symmetric_entity_link({"same_or_part": "yes", "distinct_item": "no"})


@pytest.mark.parametrize(
    "override",
    [
        {"product_index": True},
        {"product_index": 3},
        {"target_mention": "태블릿"},
        {"target_mention": " "},
        {"owner_clause_index": 1},
        {"owner_mention": "없는 구절"},
    ],
)
def test_unreviewed_or_misanchored_input_is_rejected(override):
    with pytest.raises(ValueError):
        symmetric_entity_link_messages(MESSAGE, **{**ANCHORS, **override})
