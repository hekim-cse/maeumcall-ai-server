"""A/S safety concerns pause collection until the user answers explicitly."""

import pytest

from llm.errors import AIProviderUnavailableError
from services.flow.service_workflow.contracts import (
    ScenarioStateContractError,
    compact_service_workflow_state,
    validate_service_workflow_state,
)
from services.flow.service_workflow.safety import SAFETY_CONFIRMATION_STATE, classify_safety_concern
from services.flow.support.contracts import SERVICE_REQUEST_SPEC, SUPPORT_SERVICE_REQUEST_CONTRACT


def _initial(message: str) -> dict:
    return {
        "user_message": message,
        "conversation_state": "greeting",
        "intent": SERVICE_REQUEST_SPEC.intent,
        "fields": {key: None for key in SERVICE_REQUEST_SPEC.field_keys},
        "workflow_status": "in_progress",
        "history": [],
        "recommended_replies": [],
        "should_end_call": False,
    }


def _model_says_no_safety(*args, **kwargs) -> dict:
    return {
        "intent": SERVICE_REQUEST_SPEC.intent,
        "fields": {key: None for key in SERVICE_REQUEST_SPEC.field_keys}
        | {"product_type": "휴대폰", "safety_status": "no_safety_issue"},
        "user_action": "provide_details",
        "change_field": None,
    }


def test_concern_pauses_and_confirmation_blocks_without_second_model_call(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.flow.service_workflow.nodes.classify_safety_concern", lambda message: True
    )

    def unexpected_model(*args, **kwargs):
        raise AssertionError("a pending safety concern must not enter normal extraction")

    monkeypatch.setattr(
        "services.flow.service_workflow.nodes.analyze_service_workflow_message",
        unexpected_model,
    )
    first = SUPPORT_SERVICE_REQUEST_CONTRACT.graph.invoke(
        _initial("휴대폰 충전 케이블에서 불꽃이 튄 것 같아요.")
    )
    assert first["conversation_state"] == SAFETY_CONFIRMATION_STATE
    assert first["workflow_status"] == "blocked"
    assert first["fields"]["safety_status"] is None
    assert first["fields"]["product_type"] is None
    assert first["recommended_replies"] == [
        "네, 실제로 그렇습니다.",
        "아니요, 그런 증상은 없습니다.",
        "통화를 마칠게요.",
    ]
    validate_service_workflow_state(
        SERVICE_REQUEST_SPEC, compact_service_workflow_state(SERVICE_REQUEST_SPEC, first)
    )

    monkeypatch.setattr(
        "services.flow.service_workflow.nodes.analyze_service_workflow_message",
        unexpected_model,
    )
    second = SUPPORT_SERVICE_REQUEST_CONTRACT.graph.invoke(
        {**first, "user_message": "네, 실제로 그렇습니다."}
    )
    assert second["conversation_state"] == "safety_action_required"
    assert second["fields"]["safety_status"] == "safety_issue"
    assert second["workflow_status"] == "blocked"


def test_denial_resumes_collection_and_unclear_answer_remains_paused(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.flow.service_workflow.nodes.classify_safety_concern", lambda message: None
    )
    monkeypatch.setattr(
        "services.flow.service_workflow.nodes.analyze_service_workflow_message",
        _model_says_no_safety,
    )
    first = SUPPORT_SERVICE_REQUEST_CONTRACT.graph.invoke(
        _initial("배터리 팽창인지 걱정되는데 수리 접수가 필요해요.")
    )
    assert first["conversation_state"] == SAFETY_CONFIRMATION_STATE
    monkeypatch.setattr(
        "services.flow.service_workflow.nodes.analyze_service_workflow_message",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("model called")),
    )
    unclear = SUPPORT_SERVICE_REQUEST_CONTRACT.graph.invoke(
        {**first, "user_message": "잘 모르겠어요."}
    )
    assert unclear["conversation_state"] == SAFETY_CONFIRMATION_STATE
    denied = SUPPORT_SERVICE_REQUEST_CONTRACT.graph.invoke(
        {**unclear, "user_message": "아니요, 그런 증상은 없습니다."}
    )
    assert denied["conversation_state"] == SERVICE_REQUEST_SPEC.collecting_state
    assert denied["fields"]["safety_status"] == "no_safety_issue"
    assert denied["workflow_status"] == "in_progress"


def test_pending_confirmation_can_close_without_model(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.flow.service_workflow.nodes.classify_safety_concern", lambda message: None
    )
    monkeypatch.setattr(
        "services.flow.service_workflow.nodes.analyze_service_workflow_message",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("model called")),
    )
    first = SUPPORT_SERVICE_REQUEST_CONTRACT.graph.invoke(_initial("배터리 팽창이 걱정돼요."))
    ended = SUPPORT_SERVICE_REQUEST_CONTRACT.graph.invoke(
        {**first, "user_message": "통화를 마칠게요."}
    )
    assert ended["conversation_state"] == "closing"
    assert ended["fields"]["safety_status"] is None


def test_focused_negative_keeps_normal_collection(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.flow.service_workflow.nodes.analyze_service_workflow_message",
        _model_says_no_safety,
    )
    monkeypatch.setattr(
        "services.flow.service_workflow.nodes.classify_safety_concern", lambda message: False
    )
    result = SUPPORT_SERVICE_REQUEST_CONTRACT.graph.invoke(
        _initial("다른 제품에서 불꽃이 보였다는 후기를 봤어요. 제 휴대폰은 전원이 안 켜져요.")
    )
    assert result["conversation_state"] == SERVICE_REQUEST_SPEC.collecting_state
    assert result["fields"]["safety_status"] == "no_safety_issue"


def test_pending_state_rejects_client_claim_of_confirmed_safety() -> None:
    state = compact_service_workflow_state(
        SERVICE_REQUEST_SPEC,
        {
            "intent": SERVICE_REQUEST_SPEC.intent,
            "fields": {key: None for key in SERVICE_REQUEST_SPEC.field_keys}
            | {"safety_status": "safety_issue"},
            "conversation_state": SAFETY_CONFIRMATION_STATE,
            "missing_fields": [
                key for key in SERVICE_REQUEST_SPEC.field_keys if key != "safety_status"
            ],
            "ai_message": "안전 확인",
            "user_action": "unknown",
            "change_field": None,
            "workflow_status": "blocked",
        },
    )
    with pytest.raises(ScenarioStateContractError):
        validate_service_workflow_state(SERVICE_REQUEST_SPEC, state)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"current_safety_issue": true}', True),
        ('{"current_safety_issue": false}', False),
        ('{"current_safety_issue": "true"}', None),
        ('{"current_safety_issue": true, "reason": "extra"}', None),
        ("not json", None),
    ],
)
def test_focused_classifier_accepts_only_one_boolean(monkeypatch, raw, expected) -> None:
    monkeypatch.setattr(
        "services.flow.service_workflow.safety.complete_hf_safety_json", lambda messages: raw
    )
    assert classify_safety_concern("휴대폰에서 연기가 났어요") is expected


def test_focused_classifier_retries_malformed_output_once(monkeypatch) -> None:
    responses = iter(["not json", '{"current_safety_issue": false}'])
    calls = []

    def completion(messages):
        calls.append(messages)
        return next(responses)

    monkeypatch.setattr("services.flow.service_workflow.safety.complete_hf_safety_json", completion)
    assert classify_safety_concern("불꽃이 난다는 후기를 봤어요") is False
    assert len(calls) == 2


def test_focused_classifier_failure_requires_user_confirmation(monkeypatch) -> None:
    def unavailable(messages):
        raise AIProviderUnavailableError("local model unavailable")

    monkeypatch.setattr(
        "services.flow.service_workflow.safety.complete_hf_safety_json", unavailable
    )
    assert classify_safety_concern("충전기에서 연무가 나왔어요") is None
