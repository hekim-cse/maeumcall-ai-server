"""Source provenance and safety precedence of the event-first candidate."""

from __future__ import annotations

import json

import pytest

from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v4 import contract

MESSAGE = "접수할 전기포트는 작동하지 않습니다. 토스터에서 불꽃이 났습니다."
TARGET = {"product_index": 1, "target_mention": "전기포트"}


def _raw(events: list[dict], *, overflow: bool = False) -> str:
    return json.dumps({"events": events, "overflow": overflow}, ensure_ascii=False)


def _event(index: int, quote: str, occurrence: str = "observed") -> dict:
    return {
        "event_span": {"clause_index": index, "quote": quote},
        "occurrence": occurrence,
    }


def _stage1(events: list[dict], *, overflow: bool = False) -> dict:
    return contract.validate_stage1(_raw(events, overflow=overflow), MESSAGE, **TARGET)


def test_stage1_extracts_later_other_product_hazard_without_normal_fault() -> None:
    result = _stage1([_event(2, "불꽃이 났습니다")])
    assert result["events"][0]["event_span"]["quote"] == "불꽃이 났습니다"
    assert result["events"][0]["event_span"]["start"] > 0
    prompt = contract.stage1_messages(MESSAGE, **TARGET)
    assert "전기포트" in prompt[1]["content"]
    assert "토스터에서 불꽃" in prompt[1]["content"]
    assert "owner_to_target" not in prompt[1]["content"]
    assert contract.stage1_schema(MESSAGE)["properties"]["events"]["maxItems"] == 3


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ('{"events":[],"overflow":false,"events":[]}', "duplicate_key"),
        (_raw([_event(2, "접수할")]), "quote_unanchored"),
        (_raw([_event(2, "불꽃"), _event(2, "불꽃")]), "event_order_invalid"),
        (
            _raw([_event(2, "토스터에서 불꽃이"), _event(2, "불꽃이 났습니다")]),
            "event_order_invalid",
        ),
        (_raw([_event(2, "불꽃"), _event(1, "작동하지")]), "event_order_invalid"),
        (_raw([_event(2, "불꽃")], overflow=True), "overflow_invalid"),
        (_raw([_event(2, "불꽃", "maybe")]), "occurrence_invalid"),
        (
            _raw([_event(2, "불꽃"), _event(2, "났습니다"), _event(2, "토스터")]),
            "event_order_invalid",
        ),
    ],
)
def test_stage1_rejects_unverifiable_or_inconsistent_output(raw: str, code: str) -> None:
    with pytest.raises(ValidationError) as error:
        contract.validate_stage1(raw, MESSAGE, **TARGET)
    assert error.value.code == code


@pytest.mark.parametrize(
    ("raw", "code", "field"),
    [
        (
            json.dumps({"events": [_event(2, "불꽃")], "overflow": False, "extra": True}),
            "fields_invalid",
            "stage1",
        ),
        (_raw([_event(2, "불꽃") | {"extra": True}]), "event_fields_invalid", "events[0]"),
        (_raw([_event(2, "   ")]), "quote_blank", "events[0].event_span"),
        (_raw([_event(2, " 불꽃")]), "quote_blank", "events[0].event_span"),
        (_raw([_event(2, "불꽃 ")]), "quote_blank", "events[0].event_span"),
    ],
)
def test_stage1_rejects_extra_fields_and_blank_or_padded_quotes(
    raw: str, code: str, field: str
) -> None:
    with pytest.raises(ValidationError) as error:
        contract.validate_stage1(raw, MESSAGE, **TARGET)
    assert (error.value.code, error.value.field) == (code, field)


def test_stage1_overflow_keeps_three_and_forces_confirmation() -> None:
    message = "전기포트에서 연기가 났습니다. 선이 뜨거웠습니다. 불꽃이 튀었습니다. 냄새도 났습니다."
    result = contract.validate_stage1(
        _raw(
            [
                _event(1, "연기가 났습니다"),
                _event(2, "선이 뜨거웠습니다"),
                _event(3, "불꽃이 튀었습니다"),
            ],
            overflow=True,
        ),
        message,
        product_index=1,
        target_mention="전기포트",
    )
    assert len(result["events"]) == 3
    assert (
        contract.route_for_events(
            result["events"], ["other", "other", "other"], overflow=result["overflow"]
        )
        == "confirming_safety_status"
    )


def test_stage2_anchors_owner_and_keeps_other_product_normal() -> None:
    event = _stage1([_event(2, "불꽃이 났습니다")])["events"][0]
    prompt = contract.stage2_messages(MESSAGE, event, **TARGET)
    assert "불꽃이 났습니다" in prompt[1]["content"]
    assert "subject_span" not in prompt[1]["content"]
    assert "owner_kind" not in prompt[1]["content"]
    assert contract.stage2_schema(MESSAGE)["required"] == ["hazard_owner_span", "owner_to_target"]
    raw = json.dumps(
        {
            "hazard_owner_span": {"clause_index": 2, "quote": "토스터"},
            "owner_to_target": "other",
        },
        ensure_ascii=False,
    )
    result = contract.validate_stage2(raw, MESSAGE, event, **TARGET)
    assert result["owner_to_target"] == "other"
    assert result["hazard_owner_span"]["quote"] == "토스터"
    assert contract.route_for_events([event], [result["owner_to_target"]]) == (
        "collecting_service_request"
    )


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (
            '{"owner_to_target":"current","owner_to_target":"other","hazard_owner_span":null}',
            "duplicate_key",
        ),
        ('{"owner_to_target":"current","hazard_owner_span":null}', "owner_required"),
        (
            '{"owner_to_target":"other","hazard_owner_span":{"clause_index":1,"quote":"토스터"}}',
            "quote_unanchored",
        ),
        ('{"owner_to_target":"same","hazard_owner_span":null}', "relation_invalid"),
    ],
)
def test_stage2_rejects_invalid_relation_or_quote(raw: str, code: str) -> None:
    event = _stage1([_event(2, "불꽃이 났습니다")])["events"][0]
    with pytest.raises(ValidationError) as error:
        contract.validate_stage2(raw, MESSAGE, event, **TARGET)
    assert error.value.code == code


@pytest.mark.parametrize(
    ("owner_quote", "extra", "code", "field"),
    [
        ("토스터", True, "fields_invalid", "stage2"),
        ("   ", False, "quote_blank", "hazard_owner_span"),
        (" 토스터", False, "quote_blank", "hazard_owner_span"),
        ("토스터 ", False, "quote_blank", "hazard_owner_span"),
    ],
)
def test_stage2_rejects_extra_fields_and_blank_or_padded_owner_quotes(
    owner_quote: str, extra: bool, code: str, field: str
) -> None:
    event = _stage1([_event(2, "불꽃이 났습니다")])["events"][0]
    response = {
        "hazard_owner_span": {"clause_index": 2, "quote": owner_quote},
        "owner_to_target": "other",
    }
    if extra:
        response["extra"] = True
    with pytest.raises(ValidationError) as error:
        contract.validate_stage2(json.dumps(response, ensure_ascii=False), MESSAGE, event, **TARGET)
    assert (error.value.code, error.value.field) == (code, field)


def test_stage2_rejects_tampered_event_and_nonoccurring_call() -> None:
    event = _stage1([_event(2, "불꽃이 났습니다")])["events"][0]
    event["event_span"]["start"] = 0
    with pytest.raises(ValidationError) as error:
        contract.stage2_messages(MESSAGE, event, **TARGET)
    assert error.value.code == "event_span_invalid"
    nonoccurring = _stage1([_event(2, "불꽃이 났습니다", "nonoccurring")])["events"][0]
    with pytest.raises(ValidationError) as error:
        contract.stage2_messages(MESSAGE, nonoccurring, **TARGET)
    assert error.value.code == "event_not_actionable"


@pytest.mark.parametrize(
    ("events", "relations", "overflow", "failed", "expected"),
    [
        ([], [], False, False, "collecting_service_request"),
        (["observed"], ["current"], False, False, "safety_action_required"),
        (["observed", "observed"], ["other", "current"], False, False, "safety_action_required"),
        (["observed", "observed"], ["current", "unknown"], False, False, "safety_action_required"),
        (["observed", "observed"], ["current", None], False, True, "safety_action_required"),
        (["observed"], ["other"], False, False, "collecting_service_request"),
        (["uncertain"], ["current"], False, False, "confirming_safety_status"),
        (["observed"], ["unknown"], False, False, "confirming_safety_status"),
        (["observed"], [None], False, True, "confirming_safety_status"),
        (["nonoccurring"], [None], False, False, "collecting_service_request"),
        ([], [], True, False, "confirming_safety_status"),
        ([], [], False, True, "confirming_safety_status"),
    ],
)
def test_route_precedence(
    events: list[str],
    relations: list[str | None],
    overflow: bool,
    failed: bool,
    expected: str,
) -> None:
    observed = [{"occurrence": occurrence} for occurrence in events]
    assert (
        contract.route_for_events(observed, relations, overflow=overflow, failed=failed) == expected
    )


def test_route_rejects_unreported_missing_decision() -> None:
    with pytest.raises(ValueError, match="lacks relation"):
        contract.route_for_events([{"occurrence": "observed"}], [None])
