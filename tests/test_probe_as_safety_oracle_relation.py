"""The oracle-input attribution probe remains a bounded development diagnostic."""

import json

import pytest

from scripts.probe_as_safety_oracle_relation import (
    CONFIRM,
    DIRECT,
    NORMAL,
    relation_messages,
    relation_schema,
    route_with_reviewed_event,
    validate_relation,
)

pytestmark = pytest.mark.unit


def test_schema_requires_only_one_finite_relation() -> None:
    schema = relation_schema()
    assert schema["required"] == ["source_relation"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["source_relation"]["enum"] == ["current", "other", "unknown"]


def test_prompt_keeps_full_utterance_and_both_reviewed_clauses() -> None:
    utterance = (
        "수리를 맡길 공기청정기 옆에 가습기가 있습니다. 가습기의 전원선에서 연기가 났습니다."
    )
    messages = relation_messages(
        utterance,
        product_index=1,
        hazard_index=2,
        event_status="observed",
        target_mention="수리를 맡길 공기청정기",
        hazard_event_mention="가습기의 전원선에서 연기가 났습니다",
    )
    prompt = messages[1]["content"]
    assert utterance in prompt
    assert "1. 수리를 맡길 공기청정기 옆에 가습기가 있습니다." in prompt
    assert "2. 가습기의 전원선에서 연기가 났습니다." in prompt
    assert "고정된 위험 발생 상태: observed" in prompt
    assert "검수된 접수 대상 구절: 수리를 맡길 공기청정기" in prompt
    assert "검수된 위험 사건 구절: 가습기의 전원선에서 연기가 났습니다" in prompt
    assert "문장 번호가 같다는 이유만으로" in prompt
    assert "expected_relation" not in prompt


@pytest.mark.parametrize(
    "kwargs",
    [
        {"product_index": 0, "hazard_index": 1, "event_status": "observed"},
        {"product_index": 1, "hazard_index": 2, "event_status": "observed"},
        {"product_index": True, "hazard_index": 1, "event_status": "observed"},
        {"product_index": 1, "hazard_index": 1, "event_status": "none"},
    ],
)
def test_invalid_reviewed_inputs_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        relation_messages(
            "접수 제품에서 연기가 났습니다.",
            target_mention="접수 제품",
            hazard_event_mention="연기가 났습니다",
            **kwargs,
        )


@pytest.mark.parametrize(
    ("target_mention", "hazard_event_mention"),
    [
        ("", "연기가 났습니다"),
        (" ", "연기가 났습니다"),
        ("접수 제품", " "),
        ("다른 제품", "연기가 났습니다"),
        ("접수 제품", "없는 위험"),
    ],
)
def test_oracle_mentions_must_be_in_their_reviewed_clauses(
    target_mention: str, hazard_event_mention: str
) -> None:
    with pytest.raises(ValueError, match="reviewed target or event mention"):
        relation_messages(
            "접수 제품에서 연기가 났습니다.",
            product_index=1,
            hazard_index=1,
            event_status="observed",
            target_mention=target_mention,
            hazard_event_mention=hazard_event_mention,
        )


@pytest.mark.parametrize(
    "raw",
    [
        "{}",
        '{"source_relation":"same"}',
        '{"source_relation":null}',
        '{"source_relation":true}',
        '{"source_relation":"current","hazard_index":1}',
        '{"source_relation":"current","source_relation":"other"}',
        "[]",
        "not json",
    ],
)
def test_invalid_model_output_rejected(raw: str) -> None:
    with pytest.raises((ValueError, json.JSONDecodeError)):
        validate_relation(raw)


@pytest.mark.parametrize(
    ("relation", "event_status", "expected"),
    [
        ("current", "observed", DIRECT),
        ("current", "uncertain", CONFIRM),
        ("current", "nonoccurring", NORMAL),
        ("other", "observed", NORMAL),
        ("other", "uncertain", NORMAL),
        ("unknown", "observed", CONFIRM),
        ("unknown", "uncertain", CONFIRM),
        ("unknown", "nonoccurring", NORMAL),
    ],
)
def test_reviewed_event_route(relation: str, event_status: str, expected: str) -> None:
    decision = validate_relation(json.dumps({"source_relation": relation}))
    assert route_with_reviewed_event(decision, event_status=event_status) == expected


def test_route_rejects_unvalidated_decision() -> None:
    with pytest.raises(ValueError):
        route_with_reviewed_event(
            {"source_relation": "current", "extra": "x"}, event_status="observed"
        )
