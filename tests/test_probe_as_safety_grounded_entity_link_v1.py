"""Contract checks for the development-only source-cited entity link."""

from __future__ import annotations

import json

import pytest

from scripts.probe_as_safety_grounded_entity_link_v1 import (
    grounded_entity_link_messages,
    grounded_entity_link_schema,
    validate_grounded_entity_link,
)

UTTERANCE = "수리 맡길 노트북이 켜지지 않습니다. 친구 태블릿의 충전기에서 연기가 났습니다."
ANCHORS = {
    "product_index": 1,
    "target_mention": "노트북",
    "owner_clause_index": 2,
    "owner_mention": "친구 태블릿의 충전기",
}
TARGET = {"clause_index": 1, "quote": "수리 맡길 노트북"}
OWNER = {"clause_index": 2, "quote": "친구 태블릿의 충전기"}


def _decision(link: str, evidence: list[dict]) -> str:
    return json.dumps({"entity_link": link, "evidence": evidence}, ensure_ascii=False)


def _validate(raw: str, utterance: str = UTTERANCE, **overrides) -> dict:
    anchors = {**ANCHORS, **overrides}
    return validate_grounded_entity_link(raw, utterance, **anchors)


def test_messages_preserve_full_text_and_only_reviewed_anchors():
    """No event status, relation gold, or route is supplied to the model."""
    messages = grounded_entity_link_messages(UTTERANCE, **ANCHORS)
    assert [message["role"] for message in messages] == ["system", "user"]
    prompt = messages[1]["content"]
    assert f"원문 전체: {UTTERANCE}" in prompt
    assert "1. 수리 맡길 노트북이 켜지지 않습니다." in prompt
    assert "2. 친구 태블릿의 충전기에서 연기가 났습니다." in prompt
    assert "구절 A 근거: 1." in prompt
    assert "구절 B 근거: 2." in prompt
    assert "구절 A: 노트북\n" in prompt
    assert "구절 B: 친구 태블릿의 충전기\n" in prompt
    assert "event_status" not in prompt
    assert "hazard_event_mention" not in prompt
    assert "gold_relation" not in prompt
    assert "expected_route" not in prompt


def test_schema_bounds_two_source_quotes():
    """The relation and sentence IDs are finite; quote length is bounded."""
    schema = grounded_entity_link_schema(UTTERANCE)
    assert schema["type"] == "object"
    assert schema["required"] == ["entity_link", "evidence"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["entity_link"]["enum"] == [
        "distinct_item",
        "same_or_part",
        "unresolved",
    ]
    evidence = schema["properties"]["evidence"]
    assert evidence["maxItems"] == 2
    assert evidence["items"]["properties"]["clause_index"]["enum"] == [1, 2]
    assert evidence["items"]["properties"]["quote"]["maxLength"] == len(
        "친구 태블릿의 충전기에서 연기가 났습니다."
    )
    assert evidence["items"]["additionalProperties"] is False


@pytest.mark.parametrize("link", ["same_or_part", "distinct_item"])
def test_two_clauses_require_two_quotes_containing_each_reviewed_mention(link):
    """Anchoring does not certify that the cited phrases prove the relation."""
    assert _validate(_decision(link, [TARGET, OWNER])) == {
        "entity_link": link,
        "evidence": [TARGET, OWNER],
    }


def test_one_clause_can_cover_both_mentions_with_one_quote():
    utterance = "제 노트북의 배터리에서 냄새가 납니다."
    evidence = [{"clause_index": 1, "quote": "제 노트북의 배터리"}]
    decision = _decision("same_or_part", evidence)
    assert validate_grounded_entity_link(
        decision,
        utterance,
        product_index=1,
        target_mention="노트북",
        owner_clause_index=1,
        owner_mention="배터리",
    ) == {"entity_link": "same_or_part", "evidence": evidence}


@pytest.mark.parametrize(
    "evidence",
    [
        [],
        [OWNER],
        [TARGET],
        [TARGET, {"clause_index": 3, "quote": "친구 태블릿의 충전기"}],
        [TARGET, {"clause_index": 1, "quote": "친구 태블릿의 충전기"}],
        [TARGET, {"clause_index": 2, "quote": "없는 근거"}],
        [TARGET, {"clause_index": 2, "quote": " 친구 태블릿의 충전기"}],
        [TARGET, {"clause_index": 2, "quote": "연기가"}],
    ],
)
def test_missing_or_unsupported_mention_anchor_abstains(evidence):
    """Each reviewed mention must appear in an exact quote at its clause."""
    assert _validate(_decision("distinct_item", evidence)) == {
        "entity_link": "unresolved",
        "evidence": [],
    }


def test_repeated_quote_in_claimed_clause_abstains():
    utterance = "노트북이 고장 났습니다. 충전기와 충전기가 보입니다."
    decision = _decision(
        "same_or_part",
        [{"clause_index": 1, "quote": "노트북"}, {"clause_index": 2, "quote": "충전기"}],
    )
    assert validate_grounded_entity_link(
        decision,
        utterance,
        product_index=1,
        target_mention="노트북",
        owner_clause_index=2,
        owner_mention="충전기와 충전기",
    ) == {"entity_link": "unresolved", "evidence": []}


def test_unresolved_requires_empty_evidence():
    assert _validate(_decision("unresolved", [])) == {"entity_link": "unresolved", "evidence": []}
    with pytest.raises(ValueError, match="must not cite"):
        _validate(_decision("unresolved", [TARGET, OWNER]))


@pytest.mark.parametrize(
    "raw",
    [
        '{"entity_link":"same_or_part","entity_link":"distinct_item","evidence":[]}',
        '{"entity_link":"distinct_item","evidence":[],"reason":"extra"}',
        _decision("current", [TARGET, OWNER]),
        '{"entity_link":"same_or_part","evidence":[{"clause_index":true,"quote":"노트북"}]}',
        '{"entity_link":"same_or_part","evidence":[{"clause_index":1,"quote":NaN}]}',
        '{"entity_link":"same_or_part","evidence":[{"clause_index":1,"quote":"노트북","extra":1}]}',
        _decision("distinct_item", [TARGET, OWNER, TARGET]),
        "[]",
        "{",
    ],
)
def test_malformed_or_leaky_response_is_rejected(raw):
    with pytest.raises((ValueError, json.JSONDecodeError)):
        _validate(raw)


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
def test_input_requires_reviewed_mentions_at_unique_source_clauses(override):
    with pytest.raises(ValueError):
        grounded_entity_link_messages(UTTERANCE, **{**ANCHORS, **override})
    with pytest.raises(ValueError):
        _validate(_decision("unresolved", []), **override)
