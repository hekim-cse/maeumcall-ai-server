import pytest

from llm.errors import AIResponseValidationError
from services.flow.professor.appointment.llm_structured import (
    analyze_professor_appointment_user_message,
)

pytestmark = pytest.mark.unit


def test_professor_appointment_structured_analysis_extracts_full_info(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.appointment.llm_structured.complete_hf_json",
        lambda messages: (
            """
        {
          "intent": "appointment_booking",
          "appointment_purpose": "진로 상담",
          "date": "이번 주 수요일",
          "time": "오후 3시",
          "user_name": "김개굴",
          "user_action": "provide_appointment_info"
        }
        """
        ),
    )

    result = analyze_professor_appointment_user_message(
        "greeting",
        "김개굴 학생입니다. 진로 상담 관련해서 이번 주 수요일 오후 3시에 면담 가능할까요?",
    )

    assert result["intent"] == "appointment_booking"
    assert result["appointment_purpose"] == "진로 상담"
    assert result["date"] == "이번 주 수요일"
    assert result["time"] == "오후 3시"
    assert result["user_name"] == "김개굴"
    assert result["user_action"] == "provide_appointment_info"


def test_professor_appointment_structured_analysis_handles_markdown_json(monkeypatch):
    responses = iter(
        [
            """```json
        {"intent":"appointment_booking"}
        ```""",
            '{"intent":"appointment_booking","appointment_purpose":"과제","date":"다음 주 월요일","time":"오전 10시","user_name":null,"user_action":"provide_appointment_info"}',
        ]
    )
    monkeypatch.setattr(
        "services.flow.professor.appointment.llm_structured.complete_hf_json",
        lambda messages: next(responses),
    )

    result = analyze_professor_appointment_user_message(
        "greeting",
        "과제 관련해서 다음 주 월요일 오전 10시에 면담 가능하실까요?",
    )

    assert result["appointment_purpose"] == "과제"
    assert result["date"] == "다음 주 월요일"
    assert result["time"] == "오전 10시"
    assert result["user_name"] is None
    assert result["user_action"] == "provide_appointment_info"


def test_professor_appointment_structured_analysis_rejects_invalid_json_after_retry(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.appointment.llm_structured.complete_hf_json",
        lambda messages: "면담 예약 요청으로 보입니다.",
    )

    with pytest.raises(AIResponseValidationError):
        analyze_professor_appointment_user_message("greeting", "면담 예약하고 싶습니다.")


def test_professor_appointment_structured_analysis_rejects_invalid_action(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.appointment.llm_structured.complete_hf_json",
        lambda messages: (
            """
        {
          "intent": "appointment_booking",
          "appointment_purpose": "진로 상담",
          "date": "이번 주 수요일",
          "time": "오후 3시",
          "user_name": "김개굴",
          "user_action": "invalid_action"
        }
        """
        ),
    )

    with pytest.raises(AIResponseValidationError):
        analyze_professor_appointment_user_message(
            "greeting", "김개굴 학생입니다. 진로 상담 관련 면담을 요청드립니다."
        )
