"""Keep source-span checks strict while preserving their semantic limitation."""

import pytest

from evals.structured_nlu.source_evidence import validate_source_evidence
from scripts.probe_gguf_source_evidence import evidence_contract_passed

pytestmark = pytest.mark.unit


def test_exact_korean_span_supports_a_normalized_code_without_claiming_meaning():
    utterance = "같은 음료를 다시 받을 수 있을까요?"
    quote = "다시 받을 수 있을까요"
    start = utterance.index(quote)
    validate_source_evidence(
        utterance,
        {"resolution_preference": "redelivery", "evidence_status": None},
        {"resolution_preference": {"start": start, "end": start + len(quote), "quote": quote}},
    )


@pytest.mark.parametrize(
    "evidence,error",
    [
        ({}, "evidence_field_set_mismatch"),
        ({"date": {"start": 0, "end": 2, "quote": "평일"}}, "evidence_field_set_mismatch"),
        ({"time": {"start": True, "end": 2, "quote": "평일"}}, "evidence_type_invalid"),
        ({"time": {"start": -1, "end": 2, "quote": "평일"}}, "evidence_range_invalid"),
        ({"time": {"start": 0, "end": 2, "quote": "내일"}}, "evidence_quote_mismatch"),
    ],
)
def test_invalid_or_unmatched_evidence_is_rejected_without_echoing_text(evidence, error):
    with pytest.raises(ValueError, match=error) as exc_info:
        validate_source_evidence("평일", {"time": "오전 10시", "date": None}, evidence)
    assert "오전 10시" not in str(exc_info.value)


@pytest.mark.parametrize(
    "utterance,field,value,quote",
    [
        ("평일 오전 10시", "date", "평일", "평일"),
        ("혹시 환불 가능하나요?", "resolution_preference", "refund", "환불 가능하나요"),
        ("집에서 온라인으로 발급", "issuance_channel", "government24", "온라인"),
    ],
)
def test_valid_quote_does_not_establish_field_semantics(utterance, field, value, quote):
    # Each quote exists, yet the user's exploratory labels leave these fields null.
    start = utterance.index(quote)
    validate_source_evidence(
        utterance,
        {field: value},
        {field: {"start": start, "end": start + len(quote), "quote": quote}},
    )


def test_code_point_offset_after_non_bmp_character():
    utterance = "🙂내일 예약하고 싶어요"
    validate_source_evidence(
        utterance,
        {"date": "내일"},
        {"date": {"start": 1, "end": 3, "quote": "내일"}},
    )


def test_legacy_contract_pass_is_not_evidence_contract_pass():
    assert not evidence_contract_passed(
        [{"evidence_check": "evidence_not_object"}], contract_valid=True
    )
    assert evidence_contract_passed([{"evidence_check": "valid"}], contract_valid=True)
