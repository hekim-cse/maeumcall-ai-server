import pytest
from llm.errors import AIResponseValidationError
from services.flow.reservation.hospital.llm_structured import (
    analyze_hospital_reservation_user_message,
)



pytestmark = pytest.mark.unit
def test_hospital_structured_analysis_extracts_full_info(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.hospital.llm_structured.complete_hf_json",
        lambda messages: """
        {
          "intent": "reservation",
          "department": "내과",
          "date": "내일",
          "time": "오후 3시",
          "user_action": "continue_collecting",
          "selected_time": null
        }
        """,
    )

    result = analyze_hospital_reservation_user_message(
        "greeting",
        "내일 오후 3시에 내과 진료 예약하고 싶습니다.",
    )

    assert result["intent"] == "reservation"
    assert result["department"] == "내과"
    assert result["date"] == "내일"
    assert result["time"] == "오후 3시"
    assert result["user_action"] == "continue_collecting"
    assert result["selected_time"] is None


def test_hospital_structured_analysis_handles_markdown_json(monkeypatch):
    responses = iter([
        """```json
        {"intent":"reservation"}
        ```""",
        '{"intent":"reservation","department":"피부과","date":"모레","time":"오전 10시","user_action":"confirm_reservation_info","selected_time":null}',
    ])
    monkeypatch.setattr(
        "services.flow.reservation.hospital.llm_structured.complete_hf_json",
        lambda messages: next(responses),
    )

    result = analyze_hospital_reservation_user_message(
        "confirming_info",
        "네, 맞습니다.",
    )

    assert result["intent"] == "reservation"
    assert result["department"] == "피부과"
    assert result["date"] == "모레"
    assert result["time"] == "오전 10시"
    assert result["user_action"] == "confirm_reservation_info"


def test_hospital_structured_analysis_extracts_selected_time(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.hospital.llm_structured.complete_hf_json",
        lambda messages: """
        {
          "intent": null,
          "department": null,
          "date": null,
          "time": null,
          "user_action": "select_alternative_time",
          "selected_time": "오후 4시"
        }
        """,
    )

    result = analyze_hospital_reservation_user_message(
        "suggest_alternative",
        "오후 4시로 하겠습니다.",
    )

    assert result["user_action"] == "select_alternative_time"
    assert result["selected_time"] == "오후 4시"


def test_hospital_structured_analysis_rejects_invalid_json_after_retry(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.hospital.llm_structured.complete_hf_json",
        lambda messages: "예약 도와드리겠습니다.",
    )

    with pytest.raises(AIResponseValidationError):
        analyze_hospital_reservation_user_message("greeting", "예약하고 싶습니다.")


def test_hospital_structured_analysis_rejects_invalid_action(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.hospital.llm_structured.complete_hf_json",
        lambda messages: """
        {
          "intent": "reservation",
          "department": "내과",
          "date": "내일",
          "time": "오후 3시",
          "user_action": "invalid_action",
          "selected_time": null
        }
        """,
    )

    with pytest.raises(AIResponseValidationError):
        analyze_hospital_reservation_user_message(
            "greeting", "내일 오후 3시에 내과 예약하고 싶습니다."
        )
