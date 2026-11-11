"""Contract checks for the development-only two-stage owner-resolution probe."""

from __future__ import annotations

import hashlib
import json

import pytest

from scripts.probe_as_safety_owner_resolution_v1 import (
    owner_resolution_stage1_messages,
    owner_resolution_stage1_schema,
    owner_resolution_stage2_messages,
    owner_resolution_stage2_schema,
    validate_stage1,
    validate_stage2,
)

MESSAGE = "접수할 노트북이 켜지지 않습니다. 친구 태블릿의 충전기에서 연기가 났습니다."
TARGET = {"product_index": 1, "target_mention": "노트북"}


def _quote(index: int, quote: str) -> dict:
    return {"clause_index": index, "quote": quote}


def _stage1(**changes) -> str:
    payload = {
        "event_span": _quote(2, "연기가 났습니다"),
        "subject_span": _quote(2, "친구 태블릿의 충전기"),
        "owner_span": _quote(2, "친구 태블릿"),
        "owner_kind": "explicit",
        "cue_spans": [_quote(2, "친구")],
        "distinct_cue_index": 0,
    }
    payload.update(changes)
    return json.dumps(payload, ensure_ascii=False)


def _validated(**changes) -> dict:
    return validate_stage1(_stage1(**changes), MESSAGE, **TARGET)


def test_stage1_input_exposes_only_reviewed_target_as_oracle():
    messages = owner_resolution_stage1_messages(MESSAGE, **TARGET)
    assert [item["role"] for item in messages] == ["system", "user"]
    prompt = messages[1]["content"]
    assert f"원문 전체: {MESSAGE}" in prompt
    assert "검수된 접수 대상 A 근거: 1." in prompt
    assert "접수 대상 A: 노트북" in prompt
    assert "검수된 위험 주체 B" not in prompt
    assert "expected_relation" not in prompt
    assert "event_status" not in prompt
    assert "hazard_event_mention" not in prompt


@pytest.mark.parametrize(
    "target",
    [
        {"product_index": True, "target_mention": "노트북"},
        {"product_index": 3, "target_mention": "노트북"},
        {"product_index": 1, "target_mention": "태블릿"},
    ],
)
def test_unanchored_oracle_target_is_rejected_before_model_input(target):
    with pytest.raises(ValueError):
        owner_resolution_stage1_messages(MESSAGE, **target)
    with pytest.raises(ValueError):
        validate_stage1(_stage1(), MESSAGE, **target)


def test_stage1_schema_bounds_nullable_evidence_and_distinct_cue_index():
    schema = owner_resolution_stage1_schema(MESSAGE)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["owner_kind"]["enum"] == [
        "explicit",
        "implicit_coreference",
        "unresolved",
    ]
    assert schema["properties"]["cue_spans"]["maxItems"] == 2
    assert schema["properties"]["distinct_cue_index"]["enum"] == [None, 0, 1]
    assert schema["properties"]["event_span"]["anyOf"][0]["properties"]["clause_index"]["enum"] == [
        1,
        2,
    ]


def test_exact_quote_produces_codepoint_offsets_and_hashes():
    result = _validated()
    subject = result["subject_span"]
    clause = "친구 태블릿의 충전기에서 연기가 났습니다."
    assert subject["quote"] == "친구 태블릿의 충전기"
    assert clause[subject["start"] : subject["end"]] == subject["quote"]
    assert subject["quote_sha256"] == hashlib.sha256(subject["quote"].encode()).hexdigest()
    assert result["distinct_cue_index"] == 0


def test_unicode_offsets_count_codepoints_not_utf8_bytes():
    message = "😀노트북을 맡깁니다. 친구 태블릿에서 🔥불꽃이 났습니다."
    raw = _stage1(
        event_span=_quote(2, "🔥불꽃"),
        subject_span=_quote(2, "친구 태블릿"),
        owner_span=_quote(2, "친구 태블릿"),
        cue_spans=[_quote(2, "친구")],
    )
    result = validate_stage1(raw, message, product_index=1, target_mention="노트북")
    assert result["event_span"]["start"] == len("친구 태블릿에서 ")
    assert result["event_span"]["end"] == len("친구 태블릿에서 🔥불꽃")


def test_repeated_quote_cannot_identify_one_source_occurrence():
    message = "노트북을 맡깁니다. 친구 친구 태블릿에서 연기가 났습니다."
    raw = _stage1(
        event_span=_quote(2, "연기가 났습니다"),
        subject_span=_quote(2, "친구 태블릿"),
        owner_span=_quote(2, "친구 태블릿"),
        cue_spans=[_quote(2, "친구")],
    )
    with pytest.raises(ValueError, match="uniquely anchored"):
        validate_stage1(raw, message, product_index=1, target_mention="노트북")


def test_implicit_coreference_accepts_prior_target_as_owner_antecedent():
    result = _validated(
        owner_span=_quote(1, "접수할 노트북"),
        owner_kind="implicit_coreference",
        cue_spans=[_quote(2, "충전기")],
        distinct_cue_index=None,
    )
    assert result["owner_kind"] == "implicit_coreference"
    assert result["owner_span"]["quote"] == "접수할 노트북"
    assert validate_stage2('{"source_relation":"current"}', result) == {
        "model_relation": "current",
        "effective_relation": "current",
    }


def test_stage2_receives_validated_candidates_without_gold_labels():
    stage1 = _validated()
    messages = owner_resolution_stage2_messages(MESSAGE, stage1, **TARGET)
    prompt = messages[1]["content"]
    assert MESSAGE in prompt
    assert "검증된 위험 사건 E: 2. 연기가 났습니다" in prompt
    assert "검증된 위험 주체 B: 2. 친구 태블릿의 충전기" in prompt
    assert "검증된 소속 대상 후보 C: 2. 친구 태블릿" in prompt
    assert "별도 개체 단서 후보 번호: 0" in prompt
    assert "expected_relation" not in prompt and "event_status" not in prompt
    assert owner_resolution_stage2_schema() == {
        "type": "object",
        "properties": {"source_relation": {"enum": ["current", "other", "unknown"]}},
        "required": ["source_relation"],
        "additionalProperties": False,
    }


def test_other_requires_explicit_owner_and_selected_distinct_cue():
    accepted = _validated()
    assert validate_stage2('{"source_relation":"other"}', accepted) == {
        "model_relation": "other",
        "effective_relation": "other",
    }
    no_distinct_cue = _validated(distinct_cue_index=None)
    assert (
        validate_stage2('{"source_relation":"other"}', no_distinct_cue)["effective_relation"]
        == "unknown"
    )
    implicit = _validated(
        owner_span=_quote(1, "접수할 노트북"),
        owner_kind="implicit_coreference",
        distinct_cue_index=None,
    )
    assert (
        validate_stage2('{"source_relation":"other"}', implicit)["effective_relation"] == "unknown"
    )


def test_missing_e_b_or_c_requires_stage2_skip_and_unknown_if_forced():
    for field in ("event_span", "subject_span", "owner_span"):
        changes = {field: None}
        if field == "owner_span":
            changes.update(owner_kind="unresolved", distinct_cue_index=None)
        missing = _validated(**changes)
        with pytest.raises(ValueError, match="runner must skip"):
            owner_resolution_stage2_messages(MESSAGE, missing, **TARGET)
        assert (
            validate_stage2('{"source_relation":"current"}', missing)["effective_relation"]
            == "unknown"
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"event_span": _quote(3, "연기가 났습니다")},
        {"subject_span": _quote(1, "친구 태블릿의 충전기")},
        {"owner_span": _quote(2, " 친구 태블릿")},
        {"cue_spans": [_quote(2, "없는 단서")]},
        {"cue_spans": [_quote(2, "친구")] * 3},
        {"owner_kind": "other"},
        {"owner_span": None},
        {"owner_kind": "unresolved"},
        {"distinct_cue_index": 1},
        {"distinct_cue_index": True},
    ],
)
def test_invalid_or_inconsistent_stage1_evidence_is_rejected(changes):
    with pytest.raises(ValueError):
        _validated(**changes)


@pytest.mark.parametrize(
    "raw",
    [
        '{"event_span":null,"event_span":null}',
        '{"event_span":NaN}',
        "[1,2]",
        "{",
    ],
)
def test_stage1_duplicate_nonfinite_or_malformed_json_is_rejected(raw):
    with pytest.raises((ValueError, json.JSONDecodeError)):
        validate_stage1(raw, MESSAGE, **TARGET)


@pytest.mark.parametrize(
    "raw",
    [
        '{"source_relation":"other","source_relation":"current"}',
        '{"source_relation":NaN}',
        '{"source_relation":"other","extra":1}',
        '{"source_relation":true}',
        '{"source_relation":"distinct_item"}',
        '["current"]',
        "{",
    ],
)
def test_stage2_strict_json_rejects_bad_or_leaky_output(raw):
    with pytest.raises((ValueError, json.JSONDecodeError)):
        validate_stage2(raw, _validated())
