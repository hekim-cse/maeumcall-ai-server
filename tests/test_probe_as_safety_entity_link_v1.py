"""Check the neutral two-mention contract without making a model request."""

from __future__ import annotations

import json

import pytest

from scripts.probe_as_safety_entity_link_v1 import (
    entity_link_messages,
    entity_link_schema,
    validate_entity_link,
)


def test_messages_preserve_full_text_and_only_two_oracle_anchors():
    """Do not smuggle occurrence, event, or relation labels into the request."""
    utterance = "수리 맡길 노트북이 켜지지 않습니다. 옆 태블릿의 충전기에서 연기가 났습니다."
    messages = entity_link_messages(
        utterance,
        product_index=1,
        target_mention="노트북",
        owner_clause_index=2,
        owner_mention="태블릿의 충전기",
    )
    assert len(messages) == 2
    assert [message["role"] for message in messages] == ["system", "user"]
    prompt = messages[1]["content"]
    assert f"원문 전체: {utterance}\n" in prompt
    assert "1. 수리 맡길 노트북이 켜지지 않습니다." in prompt
    assert "2. 옆 태블릿의 충전기에서 연기가 났습니다." in prompt
    assert "구절 A 근거: 1." in prompt and "구절 A: 노트북\n" in prompt
    assert "구절 B 근거: 2." in prompt and "구절 B: 태블릿의 충전기\n" in prompt
    assert "event_status" not in prompt
    assert "hazard_event_mention" not in prompt
    assert "source_relation" not in prompt
    assert "expected_relation" not in prompt
    assert "검수된 위험 사건" not in prompt


def test_schema_has_one_finite_field_and_no_text_output():
    """Constrain generation to one of three entity-link choices."""
    schema = entity_link_schema()
    assert schema["type"] == "object"
    assert schema["required"] == ["entity_link"]
    assert schema["additionalProperties"] is False
    assert schema["properties"] == {
        "entity_link": {"enum": ["distinct_item", "same_or_part", "unresolved"]}
    }


@pytest.mark.parametrize("link", ["same_or_part", "distinct_item", "unresolved"])
def test_all_finite_links_are_accepted(link):
    """Retain an explicit abstention instead of forcing a binary answer."""
    assert validate_entity_link(json.dumps({"entity_link": link})) == {"entity_link": link}


@pytest.mark.parametrize(
    "raw",
    [
        '{"entity_link":"same_or_part","entity_link":"distinct_item"}',
        '{"entity_link":"distinct_item","reason":"same model"}',
        '{"entity_link":"current"}',
        '{"entity_link":null}',
        '{"entity_link":true}',
        '{"entity_link":NaN}',
        "[]",
        "{",
    ],
)
def test_invalid_or_leaky_response_is_rejected(raw):
    """Reject duplicate keys, unbounded fields, and nonfinite values."""
    with pytest.raises((ValueError, json.JSONDecodeError)):
        validate_entity_link(raw)


@pytest.mark.parametrize(
    "overrides",
    [
        {"product_index": True},
        {"product_index": 3},
        {"target_mention": " "},
        {"target_mention": "태블릿"},
        {"owner_clause_index": 1},
        {"owner_mention": "불꽃"},
        {"owner_mention": " "},
    ],
)
def test_unreviewed_or_misanchored_input_is_rejected(overrides):
    """Require exact, unique source mentions before a call is prepared."""
    values = {
        "product_index": 1,
        "target_mention": "노트북",
        "owner_clause_index": 2,
        "owner_mention": "태블릿의 충전기",
    }
    values.update(overrides)
    with pytest.raises(ValueError):
        entity_link_messages(
            "수리 맡길 노트북이 켜지지 않습니다. 옆 태블릿의 충전기에서 연기가 났습니다.",
            **values,
        )


def test_repeated_quote_in_one_clause_is_rejected():
    """A noun repeated in one sentence cannot identify a unique entity."""
    with pytest.raises(ValueError):
        entity_link_messages(
            "노트북 옆 노트북이 고장 났습니다. 충전기에서 연기가 났습니다.",
            product_index=1,
            target_mention="노트북",
            owner_clause_index=2,
            owner_mention="충전기",
        )


def test_text_anchor_does_not_claim_to_validate_owner_semantics():
    """An in-text quote can be wrong as an owner; review is an upstream input."""
    messages = entity_link_messages(
        "수리 맡길 노트북이 켜지지 않습니다. 옆 태블릿의 충전기에서 연기가 났습니다.",
        product_index=1,
        target_mention="노트북",
        owner_clause_index=2,
        owner_mention="연기",
    )
    assert "구절 B: 연기\n" in messages[1]["content"]
