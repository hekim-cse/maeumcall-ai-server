"""Synthetic contract and safety-boundary checks for a limited deterministic baseline."""

import pytest

from experiments.as_safety_explicit_baseline_v1.contract import predict_relation
from experiments.as_safety_v2.json_contract import ValidationError


def _span(quote: str, clause_index: int = 1) -> dict:
    return {"clause_index": clause_index, "quote": quote}


@pytest.mark.parametrize(
    ("message", "target", "event", "owner", "expected_relation", "expected_basis"),
    [
        (
            "로봇청소기 전원 연결부에서 연기가 났어요.",
            _span("로봇청소기"),
            _span("연기가 났어요"),
            _span("로봇청소기 전원 연결부"),
            "current",
            "target_prefix_candidate",
        ),
        (
            "로봇청소기에서 연기가 났어요.",
            _span("로봇청소기"),
            _span("연기가 났어요"),
            _span("로봇청소기"),
            "current",
            "exact_target",
        ),
        (
            "로봇청소기를 접수합니다. 다른 기기의 충전기에서 불꽃이 났어요.",
            _span("로봇청소기"),
            _span("불꽃이 났어요", 2),
            _span("다른 기기의 충전기", 2),
            "other",
            "explicit_other_device",
        ),
        (
            "로봇청소기를 접수합니다. 다른 기기에서 불꽃이 났어요.",
            _span("로봇청소기"),
            _span("불꽃이 났어요", 2),
            _span("다른 기기", 2),
            "other",
            "explicit_other_device",
        ),
        (
            "다른 로봇청소기 전원 연결부에서 연기가 났어요.",
            _span("로봇청소기"),
            _span("연기가 났어요"),
            _span("다른 로봇청소기 전원 연결부"),
            "unknown",
            "conflicting_context",
        ),
        (
            "다른 로봇청소기에서 연기가 났어요.",
            _span("로봇청소기"),
            _span("연기가 났어요"),
            _span("로봇청소기"),
            "unknown",
            "conflicting_context",
        ),
        (
            "에어프라이어를 접수합니다. 그 제품의 손잡이에서 연기가 났어요.",
            _span("에어프라이어"),
            _span("연기가 났어요", 2),
            _span("그 제품의 손잡이", 2),
            "unknown",
            "insufficient_evidence",
        ),
        (
            "스마트워치를 접수합니다. 시계 뒷면이 뜨거워졌어요.",
            _span("스마트워치"),
            _span("뜨거워졌어요", 2),
            _span("시계 뒷면", 2),
            "unknown",
            "insufficient_evidence",
        ),
        (
            "식기세척기를 접수합니다. 전기밥솥 전원선에서 불꽃이 났어요.",
            _span("식기세척기"),
            _span("불꽃이 났어요", 2),
            _span("전기밥솥 전원선", 2),
            "unknown",
            "insufficient_evidence",
        ),
        (
            "로봇청소기 방문 비용이 궁금한데 연기가 났어요.",
            _span("로봇청소기"),
            _span("연기가 났어요"),
            _span("로봇청소기 방문 비용"),
            "current",
            "target_prefix_candidate",
        ),
    ],
)
def test_lexical_relation_is_narrow_but_prefix_is_not_semantic_proof(
    message, target, event, owner, expected_relation, expected_basis
):
    result = predict_relation(
        message,
        target=target,
        event_span=event,
        hazard_owner_span=owner,
        occurrence="observed",
    )
    assert result == {"relation": expected_relation, "basis": expected_basis}


def test_missing_owner_abstains_without_guessing_from_event():
    result = predict_relation(
        "휴대용 라디오에서 탄 냄새가 나는 것 같아요.",
        target=_span("휴대용 라디오"),
        event_span=_span("탄 냄새가 나는 것 같아요"),
        hazard_owner_span=None,
        occurrence="observed",
    )
    assert result == {"relation": "unknown", "basis": "owner_missing"}


def test_nonoccurring_event_has_no_relation():
    result = predict_relation(
        "선풍기에서 연기가 날까 걱정돼요.",
        target=_span("선풍기"),
        event_span=_span("연기가 날까 걱정돼요"),
        hazard_owner_span=None,
        occurrence="nonoccurring",
    )
    assert result == {"relation": None, "basis": "nonoccurring"}


def test_invalid_or_ambiguous_source_quote_is_rejected():
    with pytest.raises(ValidationError, match="quote_unanchored"):
        predict_relation(
            "식기세척기 전원선에서 불꽃이 튀었어요.",
            target=_span("식기세척기"),
            event_span=_span("연기가 났어요"),
            hazard_owner_span=_span("식기세척기 전원선"),
            occurrence="observed",
        )
    with pytest.raises(ValidationError, match="quote_nonunique"):
        predict_relation(
            "식기세척기 전원선에서 식기세척기 불꽃이 튀었어요.",
            target=_span("식기세척기"),
            event_span=_span("불꽃이 튀었어요"),
            hazard_owner_span=_span("식기세척기 전원선"),
            occurrence="observed",
        )


def test_nonoccurring_owner_is_rejected():
    with pytest.raises(ValidationError, match="nonoccurring_owner_invalid"):
        predict_relation(
            "선풍기에서 연기가 날까 걱정돼요.",
            target=_span("선풍기"),
            event_span=_span("연기가 날까 걱정돼요"),
            hazard_owner_span=_span("선풍기"),
            occurrence="nonoccurring",
        )


@pytest.mark.parametrize("spaces", [" ", "  ", "   "])
def test_usage_phrase_stays_unknown_with_extra_spacing(spaces):
    message = f"로봇청소기{spaces}용 충전기에서 연기가 났어요."
    assert predict_relation(
        message,
        target=_span("로봇청소기"),
        event_span=_span("연기가 났어요"),
        hazard_owner_span=_span(f"로봇청소기{spaces}용 충전기"),
        occurrence="observed",
    ) == {"relation": "unknown", "basis": "insufficient_evidence"}


def test_invalid_occurrence_and_extra_quote_field_are_rejected():
    message = "로봇청소기 전원 연결부에서 연기가 났어요."
    args = {
        "target": _span("로봇청소기"),
        "event_span": _span("연기가 났어요"),
        "hazard_owner_span": _span("로봇청소기 전원 연결부"),
    }
    with pytest.raises(ValidationError, match="occurrence_invalid"):
        predict_relation(message, occurrence="Observed", **args)
    with pytest.raises(ValidationError, match="quote_fields_invalid"):
        predict_relation(
            message,
            occurrence="observed",
            **(args | {"hazard_owner_span": args["hazard_owner_span"] | {"extra": 1}}),
        )
    with pytest.raises(ValidationError, match="quote_blank"):
        predict_relation(
            message,
            occurrence="observed",
            **(args | {"hazard_owner_span": _span(" 로봇청소기 전원 연결부")}),
        )
