"""Tests for the smaller development-only A/S extraction contract."""

import hashlib
import json

import pytest

from experiments.as_safety_v2.extraction import (
    stage1_messages,
    stage1_schema,
    validate_stage1,
)
from experiments.as_safety_v2.json_contract import ValidationError

MESSAGE = "접수할 노트북이 켜지지 않습니다. 친구 태블릿의 충전기에서 연기가 났습니다."
TARGET = {"product_index": 1, "target_mention": "노트북"}


def _payload(**changes) -> dict:
    payload = {
        "event_span": {"clause_index": 2, "quote": "연기가 났습니다"},
        "subject_span": {"clause_index": 2, "quote": "친구 태블릿의 충전기"},
        "owner_span": {"clause_index": 2, "quote": "친구 태블릿"},
        "owner_kind": "explicit",
    }
    return payload | changes


def _validate(**changes) -> dict:
    return validate_stage1(json.dumps(_payload(**changes), ensure_ascii=False), MESSAGE, **TARGET)


def test_prompt_supplies_only_target_oracle_and_no_fake_quote_example():
    messages = stage1_messages(MESSAGE, **TARGET)
    assert [message["role"] for message in messages] == ["system", "user"]
    prompt = "\n".join(message["content"] for message in messages)
    assert MESSAGE in prompt
    assert "검수된 접수 대상 A: 1. 노트북" in prompt
    assert '"quote":"원문"' not in prompt
    assert "cue_spans" not in prompt and "distinct_cue_index" not in prompt
    assert "검수된 위험 주체" not in prompt
    assert "expected_relation" not in prompt and "event_status" not in prompt
    assert "친구 태블릿" in prompt  # present only as part of the original utterance


def test_schema_has_only_four_required_fields():
    schema = stage1_schema(MESSAGE)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert (
        set(schema["required"])
        == set(schema["properties"])
        == {"event_span", "subject_span", "owner_span", "owner_kind"}
    )
    assert schema["properties"]["event_span"]["anyOf"][0]["properties"]["clause_index"] == {
        "enum": [1, 2]
    }


def test_valid_anchors_include_codepoint_offsets_and_hash():
    result = _validate()
    subject = result["subject_span"]
    clause = "친구 태블릿의 충전기에서 연기가 났습니다."
    assert clause[subject["start"] : subject["end"]] == subject["quote"]
    assert subject["quote_sha256"] == hashlib.sha256(subject["quote"].encode()).hexdigest()


@pytest.mark.parametrize(
    ("changes", "code", "field"),
    [
        ({"owner_kind": "other"}, "owner_kind_invalid", "owner_kind"),
        ({"owner_span": None}, "owner_consistency_invalid", "owner_span"),
        ({"owner_kind": "unresolved"}, "owner_consistency_invalid", "owner_span"),
        ({"event_span": {"clause_index": 2, "quote": "원문"}}, "quote_unanchored", "event_span"),
        (
            {"subject_span": {"clause_index": 1, "quote": "친구 태블릿"}},
            "quote_unanchored",
            "subject_span",
        ),
        (
            {"owner_span": {"clause_index": 3, "quote": "친구 태블릿"}},
            "quote_index_invalid",
            "owner_span",
        ),
        ({"cue_spans": []}, "fields_invalid", "stage1"),
    ],
)
def test_invalid_output_has_finite_field_specific_error(changes, code, field):
    with pytest.raises(ValidationError) as caught:
        _validate(**changes)
    assert (caught.value.code, caught.value.field) == (code, field)


def test_null_owner_requires_unresolved_kind():
    result = _validate(owner_span=None, owner_kind="unresolved")
    assert result["owner_span"] is None
    assert result["owner_kind"] == "unresolved"


def test_duplicate_key_rejection_is_not_hidden_by_missing_fields():
    valid = json.dumps(_payload(), ensure_ascii=False)
    duplicate = valid.replace('"event_span":', '"event_span": null, "event_span":', 1)
    assert json.loads(duplicate) == json.loads(valid)
    with pytest.raises(ValidationError) as caught:
        validate_stage1(duplicate, MESSAGE, **TARGET)
    assert caught.value.code == "duplicate_key"


@pytest.mark.parametrize(
    "product_index,target_mention", [(True, "노트북"), (3, "노트북"), (1, "태블릿")]
)
def test_target_must_be_anchored_before_prompt_or_validation(product_index, target_mention):
    with pytest.raises(ValidationError):
        stage1_messages(MESSAGE, product_index=product_index, target_mention=target_mention)
    with pytest.raises(ValidationError):
        validate_stage1(
            json.dumps(_payload(), ensure_ascii=False),
            MESSAGE,
            product_index=product_index,
            target_mention=target_mention,
        )
