"""Stage-two relation and conservative separate-entity cue checks."""

import json

import pytest

from experiments.as_safety_v2.extraction import validate_stage1
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.relation import (
    stage2_messages,
    stage2_schema,
    validate_stage2,
)

MESSAGE = "접수할 노트북이 켜지지 않습니다. 친구 태블릿의 충전기에서 연기가 났습니다."
TARGET = {"product_index": 1, "target_mention": "노트북"}


def _stage1(*, owner_kind="explicit", missing=None) -> dict:
    payload = {
        "event_span": {"clause_index": 2, "quote": "연기가 났습니다"},
        "subject_span": {"clause_index": 2, "quote": "친구 태블릿의 충전기"},
        "owner_span": {"clause_index": 2, "quote": "친구 태블릿"},
        "owner_kind": owner_kind,
    }
    if missing is not None:
        payload[missing] = None
        if missing == "owner_span":
            payload["owner_kind"] = "unresolved"
    return validate_stage1(json.dumps(payload, ensure_ascii=False), MESSAGE, **TARGET)


def _raw(relation="other", cue=None) -> str:
    if cue is None and relation == "other":
        cue = {"clause_index": 2, "quote": "친구 태블릿"}
    return json.dumps(
        {"source_relation": relation, "distinct_evidence_span": cue}, ensure_ascii=False
    )


def _validate(raw, stage1=None):
    return validate_stage2(raw, MESSAGE, _stage1() if stage1 is None else stage1, **TARGET)


def test_stage_two_uses_only_original_and_stage_one_candidates():
    messages = stage2_messages(MESSAGE, _stage1(), **TARGET)
    prompt = "\n".join(message["content"] for message in messages)
    assert MESSAGE in prompt
    assert "접수 대상 A: 1. 노트북" in prompt
    assert "위험 사건 E 후보: 2. 연기가 났습니다" in prompt
    assert "위험 주체 B 후보: 2. 친구 태블릿의 충전기" in prompt
    assert "소속 대상 C 후보: 2. 친구 태블릿" in prompt
    assert '"quote":"원문"' not in prompt
    assert "gold_relation" not in prompt and "expected_route" not in prompt


def test_stage_two_schema_limits_relation_and_clause_ids():
    schema = stage2_schema(MESSAGE)
    assert schema["additionalProperties"] is False
    assert (
        set(schema["required"])
        == set(schema["properties"])
        == {"source_relation", "distinct_evidence_span"}
    )
    assert schema["properties"]["source_relation"]["enum"] == ["current", "other", "unknown"]
    assert schema["properties"]["distinct_evidence_span"]["anyOf"][0]["properties"]["clause_index"][
        "enum"
    ] == [1, 2]


def test_other_with_explicit_owner_and_anchored_distinct_cue_is_effective():
    result = _validate(_raw())
    assert result["model_relation"] == result["effective_relation"] == "other"
    assert result["distinct_evidence_span"]["quote"] == "친구 태블릿"
    assert result["distinct_evidence_span"]["start"] >= 0


def test_other_without_cue_is_demoted_but_raw_relation_retained():
    raw = '{"source_relation":"other","distinct_evidence_span":null}'
    result = _validate(raw)
    assert result["model_relation"] == "other"
    assert result["effective_relation"] == "unknown"
    assert result["distinct_evidence_span"] is None


def test_other_with_implicit_owner_is_demoted_even_with_cue():
    result = _validate(_raw(), _stage1(owner_kind="implicit_coreference"))
    assert result["model_relation"] == "other"
    assert result["effective_relation"] == "unknown"


@pytest.mark.parametrize("missing", ["event_span", "subject_span", "owner_span"])
def test_missing_stage_one_evidence_forces_stage_two_skip(missing):
    stage1 = _stage1(missing=missing)
    with pytest.raises(ValidationError) as caught:
        stage2_messages(MESSAGE, stage1, **TARGET)
    assert (caught.value.code, caught.value.field) == ("stage1_incomplete", missing)
    with pytest.raises(ValidationError):
        _validate(_raw(), stage1)


@pytest.mark.parametrize(
    ("raw", "code", "field"),
    [
        ('{"source_relation":"other"}', "fields_invalid", "stage2"),
        (
            '{"source_relation":"different","distinct_evidence_span":null}',
            "relation_invalid",
            "source_relation",
        ),
        (
            '{"source_relation":"current","distinct_evidence_span":{"clause_index":2,"quote":"친구"}}',
            "distinct_evidence_inconsistent",
            "distinct_evidence_span",
        ),
        (
            '{"source_relation":"other","distinct_evidence_span":{"clause_index":2,"quote":"원문"}}',
            "quote_unanchored",
            "distinct_evidence_span",
        ),
        (
            '{"source_relation":"other","distinct_evidence_span":{"clause_index":3,"quote":"친구"}}',
            "quote_index_invalid",
            "distinct_evidence_span",
        ),
        ('{"source_relation":"other","distinct_evidence_span":NaN}', "nonfinite_number", "$"),
    ],
)
def test_invalid_stage_two_output_has_finite_field_specific_error(raw, code, field):
    with pytest.raises(ValidationError) as caught:
        _validate(raw)
    assert (caught.value.code, caught.value.field) == (code, field)


def test_duplicate_relation_key_is_rejected():
    valid = _raw()
    duplicate = valid.replace(
        '"source_relation":', '"source_relation": "unknown", "source_relation":', 1
    )
    assert json.loads(duplicate) == json.loads(valid)
    with pytest.raises(ValidationError) as caught:
        _validate(duplicate)
    assert caught.value.code == "duplicate_key"


def test_valid_current_and_unknown_require_no_distinct_cue():
    for relation in ("current", "unknown"):
        result = _validate(_raw(relation))
        assert result["model_relation"] == result["effective_relation"] == relation
        assert result["distinct_evidence_span"] is None


def test_corrupt_stage_one_offsets_are_rejected_before_prompt():
    stage1 = _stage1()
    stage1["owner_span"]["start"] += 1
    with pytest.raises(ValidationError) as caught:
        stage2_messages(MESSAGE, stage1, **TARGET)
    assert (caught.value.code, caught.value.field) == ("stage1_span_invalid", "owner_span")
