"""Explicit hazards must reach the A/S guard even if model extraction fails."""

import pytest

from services.flow.service_workflow.contracts import validate_service_workflow_state
from services.flow.service_workflow.safety import has_explicit_safety_issue
from services.flow.support.contracts import SERVICE_REQUEST_SPEC, SUPPORT_SERVICE_REQUEST_CONTRACT


@pytest.mark.parametrize(
    "message",
    (
        "배터리가 부풀어 올라 충전할 때 뜨거워집니다.",
        "충전 단자에서 타는 냄새가 납니다.",
        "공기청정기에서 연기가 나서 전원을 껐습니다.",
        "기기에서 연기가 발생합니다.",
        "배터리가 부풀고 기기가 뜨겁습니다.",
        "배터리가 부풀었습니다.",
        "기기가 뜨거워집니다.",
    ),
)
def test_explicit_hazard_phrases_are_detected(message: str) -> None:
    assert has_explicit_safety_issue(message)


@pytest.mark.parametrize(
    "message",
    (
        "배터리가 부풀지 않았습니다.",
        "배터리가 부풀었는지 확인하고 싶습니다.",
        "배터리는 부풀지 않았고 보호 필름이 부풀었습니다.",
        "배터리가 부풀었다면 어떻게 하나요?",
        "연기는 나지 않습니다.",
        "연기가 발생하지 않습니다.",
        "기기에서 연기가 발생할까요?",
        "타는 냄새는 안 납니다.",
        "기기가 뜨거워지지 않았습니다.",
        "연기가 날 수도 있는지 걱정입니다.",
        "교체용 배터리 가격을 알고 싶습니다.",
    ),
)
def test_negated_hypothetical_or_unrelated_phrases_do_not_trigger(message: str) -> None:
    assert not has_explicit_safety_issue(message)


@pytest.mark.parametrize(
    "message",
    (
        "휴대폰 배터리가 부풀어 올라 있습니다.",
        "휴대폰에서 연기가 발생합니다.",
        "휴대폰 충전 단자에서 타는 냄새가 납니다.",
        "기기가 뜨거워집니다.",
    ),
)
def test_safety_route_does_not_depend_on_model_output(
    monkeypatch: pytest.MonkeyPatch, message: str
) -> None:
    def model_should_not_be_called(*args, **kwargs):
        raise AssertionError("explicit hazard must bypass model extraction")

    monkeypatch.setattr(
        "services.flow.service_workflow.nodes.analyze_service_workflow_message",
        model_should_not_be_called,
    )
    result = SUPPORT_SERVICE_REQUEST_CONTRACT.graph.invoke(
        {
            "user_message": message,
            "conversation_state": "greeting",
            "intent": SERVICE_REQUEST_SPEC.intent,
            "fields": {key: None for key in SERVICE_REQUEST_SPEC.field_keys},
            "workflow_status": "in_progress",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )
    assert result["fields"]["safety_status"] == "safety_issue"
    assert result["conversation_state"] == "safety_action_required"
    assert result["workflow_status"] == "blocked"
    assert "사용과 충전" in result["ai_message"]
    validate_service_workflow_state(SERVICE_REQUEST_SPEC, result)


def test_safety_state_can_close_when_hazard_is_repeated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "services.flow.service_workflow.nodes.analyze_service_workflow_message",
        lambda *args, **kwargs: {
            "intent": SERVICE_REQUEST_SPEC.intent,
            "fields": {key: None for key in SERVICE_REQUEST_SPEC.field_keys},
            "user_action": "go_closing",
            "change_field": None,
        },
    )
    fields = {key: None for key in SERVICE_REQUEST_SPEC.field_keys}
    fields["safety_status"] = "safety_issue"
    result = SUPPORT_SERVICE_REQUEST_CONTRACT.graph.invoke(
        {
            "user_message": "배터리가 부풀었습니다. 충전을 멈췄고 통화를 마칠게요.",
            "conversation_state": "safety_action_required",
            "intent": SERVICE_REQUEST_SPEC.intent,
            "fields": fields,
            "workflow_status": "blocked",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )
    assert result["conversation_state"] == "closing"
