"""Conditional Stage2 owner-link contract and prompt boundary."""

import json

import pytest

from experiments.as_safety_v2.extraction import validate_stage1
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v3.relation import (
    stage2_messages,
    stage2_schema,
    validate_stage2,
)

MESSAGE = "접수할 노트북이 켜지지 않습니다. 친구 태블릿의 충전기에서 연기가 났습니다."
TARGET = {"product_index": 1, "target_mention": "노트북"}


def _stage1(owner_kind="explicit") -> dict:
    payload = {
        "event_span": {"clause_index": 2, "quote": "연기가 났습니다"},
        "subject_span": {"clause_index": 2, "quote": "친구 태블릿의 충전기"},
        "owner_span": {"clause_index": 2, "quote": "친구 태블릿"},
        "owner_kind": owner_kind,
    }
    return validate_stage1(json.dumps(payload, ensure_ascii=False), MESSAGE, **TARGET)


def _raw(link="distinct", owner=None) -> str:
    if owner is None and link == "distinct":
        owner = {"clause_index": 2, "quote": "친구 태블릿의 충전기"}
    return json.dumps({"owner_to_target": link, "hazard_owner_span": owner}, ensure_ascii=False)


def _validate(raw, stage1=None):
    return validate_stage2(raw, MESSAGE, _stage1() if stage1 is None else stage1, **TARGET)


def test_messages_use_source_and_stage1_event_subject_but_not_owner_candidate():
    messages = stage2_messages(MESSAGE, _stage1(), **TARGET)
    prompt = "\n".join(message["content"] for message in messages)
    assert MESSAGE in prompt
    assert "접수 대상 A: 1. 노트북" in prompt
    assert "위험 사건 E 후보: 2. 연기가 났습니다" in prompt
    assert "위험 주체 B 후보: 2. 친구 태블릿의 충전기" in prompt
    assert "소속 대상 C 후보" not in prompt
    assert "owner_kind" not in prompt
    assert "implicit_coreference" not in prompt
    assert "gold_relation" not in prompt and "expected_route" not in prompt


def test_owner_kind_does_not_change_prompt_or_validation():
    explicit = _stage1("explicit")
    implicit = _stage1("implicit_coreference")
    assert stage2_messages(MESSAGE, explicit, **TARGET) == stage2_messages(
        MESSAGE, implicit, **TARGET
    )
    assert _validate(_raw(), explicit) == _validate(_raw(), implicit)


def test_schema_has_only_two_fields_and_source_clause_ids():
    schema = stage2_schema(MESSAGE)
    assert schema["additionalProperties"] is False
    assert (
        set(schema["required"])
        == set(schema["properties"])
        == {
            "hazard_owner_span",
            "owner_to_target",
        }
    )
    assert schema["properties"]["owner_to_target"]["enum"] == [
        "coreference",
        "distinct",
        "part_of",
        "same",
        "unclear",
    ]
    assert schema["properties"]["hazard_owner_span"]["anyOf"][0]["properties"]["clause_index"][
        "enum"
    ] == [1, 2]


@pytest.mark.parametrize(
    ("link", "expected"),
    [
        ("same", "current"),
        ("part_of", "current"),
        ("coreference", "current"),
        ("distinct", "other"),
        ("unclear", "unknown"),
    ],
)
def test_link_mapping_preserves_raw_choice(link, expected):
    owner = {"clause_index": 2, "quote": "친구 태블릿의 충전기"}
    result = _validate(_raw(link, owner))
    assert result["model_link"] == link
    assert result["effective_relation"] == expected
    assert result["hazard_owner_span"]["quote"] == owner["quote"]


def test_unclear_may_have_no_identifiable_owner():
    result = _validate(_raw("unclear"))
    assert result == {
        "model_link": "unclear",
        "effective_relation": "unknown",
        "hazard_owner_span": None,
    }


@pytest.mark.parametrize(
    ("raw", "code", "field"),
    [
        ('{"owner_to_target":"distinct"}', "fields_invalid", "stage2"),
        (
            '{"owner_to_target":"unclear","hazard_owner_span":null,"extra":1}',
            "fields_invalid",
            "stage2",
        ),
        (
            '{"owner_to_target":"different","hazard_owner_span":null}',
            "link_invalid",
            "owner_to_target",
        ),
        (
            '{"owner_to_target":"same","hazard_owner_span":null}',
            "owner_required",
            "hazard_owner_span",
        ),
        (
            '{"owner_to_target":"distinct","hazard_owner_span":{"clause_index":2,"quote":"원문에 없음"}}',
            "quote_unanchored",
            "hazard_owner_span",
        ),
        (
            '{"owner_to_target":"distinct","hazard_owner_span":{"clause_index":2,"quote":" "}}',
            "quote_blank",
            "hazard_owner_span",
        ),
        (
            '{"owner_to_target":"distinct","hazard_owner_span":{"clause_index":3,"quote":"충전기"}}',
            "quote_index_invalid",
            "hazard_owner_span",
        ),
        (
            '{"owner_to_target":"unclear","hazard_owner_span":NaN}',
            "nonfinite_number",
            "$",
        ),
    ],
)
def test_bad_outputs_have_finite_field_specific_errors(raw, code, field):
    with pytest.raises(ValidationError) as caught:
        _validate(raw)
    assert (caught.value.code, caught.value.field) == (code, field)


def test_duplicate_key_is_rejected_without_echoing_raw_key():
    with pytest.raises(ValidationError) as caught:
        _validate(
            '{"owner_to_target":"same","owner_to_target":"distinct","hazard_owner_span":null}'
        )
    assert (caught.value.code, caught.value.field) == ("duplicate_key", "$")


def test_missing_event_or_subject_skips_before_prompt_and_validation():
    for field in ("event_span", "subject_span"):
        stage1 = _stage1()
        stage1[field] = None
        with pytest.raises(ValidationError) as caught:
            stage2_messages(MESSAGE, stage1, **TARGET)
        assert (caught.value.code, caught.value.field) == ("stage1_incomplete", field)
        with pytest.raises(ValidationError):
            _validate(_raw(), stage1)


def test_corrupted_stage1_candidate_offsets_are_rejected():
    stage1 = _stage1()
    stage1["event_span"]["start"] += 1
    with pytest.raises(ValidationError) as caught:
        stage2_messages(MESSAGE, stage1, **TARGET)
    assert (caught.value.code, caught.value.field) == ("stage1_span_invalid", "event_span")


def test_product_target_must_be_anchored_to_its_clause():
    with pytest.raises(ValidationError) as caught:
        stage2_messages(MESSAGE, _stage1(), product_index=2, target_mention="노트북")
    assert (caught.value.code, caught.value.field) == ("target_unanchored", "target_mention")
