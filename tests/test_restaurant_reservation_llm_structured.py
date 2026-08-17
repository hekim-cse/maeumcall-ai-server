import pytest

from llm.errors import AIResponseValidationError
from services.flow.reservation.restaurant.llm_structured import (
    analyze_restaurant_reservation_user_message,
)

pytestmark = pytest.mark.unit


def test_restaurant_structured_analysis_extracts_full_info(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.restaurant.llm_structured.complete_hf_json",
        lambda messages: (
            """
        {
          "intent": "reservation",
          "date": "내일",
          "time": "저녁 7시",
          "party_size": "4명",
          "user_name": "김개굴",
          "user_action": "continue_collecting",
          "selected_time": null
        }
        """
        ),
    )

    result = analyze_restaurant_reservation_user_message(
        "greeting",
        "내일 저녁 7시에 4명 김개굴 이름으로 예약하고 싶습니다.",
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "내일"
    assert result["time"] == "저녁 7시"
    assert result["party_size"] == "4명"
    assert result["user_name"] == "김개굴"
    assert result["user_action"] == "continue_collecting"
    assert result["selected_time"] is None


def test_restaurant_structured_analysis_handles_markdown_json(monkeypatch):
    responses = iter(
        [
            """```json
        {"intent":"reservation"}
        ```""",
            '{"intent":"reservation","date":"이번 주말","time":"오후 6시","party_size":"2명","user_name":"김개굴","user_action":"continue_collecting","selected_time":null}',
        ]
    )
    monkeypatch.setattr(
        "services.flow.reservation.restaurant.llm_structured.complete_hf_json",
        lambda messages: next(responses),
    )

    result = analyze_restaurant_reservation_user_message(
        "greeting",
        "이번 주말 오후 6시에 2명 예약할게요.",
    )

    assert result["date"] == "이번 주말"
    assert result["time"] == "오후 6시"
    assert result["party_size"] == "2명"
    assert result["user_action"] == "continue_collecting"


def test_restaurant_structured_analysis_extracts_selected_time(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.restaurant.llm_structured.complete_hf_json",
        lambda messages: (
            """
        {
          "intent": "reservation",
          "date": null,
          "time": null,
          "party_size": null,
          "user_name": null,
          "user_action": "select_alternative_time",
          "selected_time": "저녁 8시"
        }
        """
        ),
    )

    result = analyze_restaurant_reservation_user_message(
        "reservation_unavailable",
        "저녁 8시로 할게요.",
    )

    assert result["user_action"] == "select_alternative_time"
    assert result["selected_time"] == "저녁 8시"


def test_restaurant_structured_analysis_rejects_invalid_json_after_retry(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.restaurant.llm_structured.complete_hf_json",
        lambda messages: "예약 가능합니다.",
    )

    with pytest.raises(AIResponseValidationError):
        analyze_restaurant_reservation_user_message("greeting", "식당 예약하고 싶습니다.")


def test_restaurant_structured_analysis_rejects_invalid_action(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.restaurant.llm_structured.complete_hf_json",
        lambda messages: (
            """
        {
          "intent": "reservation",
          "date": "내일",
          "time": "저녁 7시",
          "party_size": "4명",
          "user_name": "김개굴",
          "user_action": "invalid_action",
          "selected_time": null
        }
        """
        ),
    )

    with pytest.raises(AIResponseValidationError):
        analyze_restaurant_reservation_user_message(
            "greeting", "내일 저녁 7시에 4명 김개굴 이름으로 예약하고 싶습니다."
        )
