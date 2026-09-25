import pytest

from llm.errors import AIResponseValidationError
from services.flow.reservation.hospital.llm_structured import (
    analyze_hospital_reservation_user_message,
)

pytestmark = pytest.mark.unit


def test_hospital_structured_analysis_extracts_full_info(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.hospital.llm_structured.complete_hf_json",
        lambda messages: (
            """
        {
          "intent": "reservation",
          "department": "내과",
          "date": "내일",
          "time": "오후 3시",
          "user_name": "김개굴",
          "user_action": "continue_collecting",
          "selected_time": null
        }
        """
        ),
    )

    result = analyze_hospital_reservation_user_message(
        "greeting",
        "내일 오후 3시에 내과 진료 예약하고 싶습니다.",
    )

    assert result["intent"] == "reservation"
    assert result["department"] == "내과"
    assert result["date"] == "내일"
    assert result["time"] == "오후 3시"
    assert result["user_name"] == "김개굴"
    assert result["user_action"] == "continue_collecting"
    assert result["selected_time"] is None


def test_hospital_structured_analysis_handles_markdown_json(monkeypatch):
    responses = iter(
        [
            """```json
        {"intent":"reservation"}
        ```""",
            '{"intent":"reservation","department":null,"date":null,"time":null,"user_name":null,"user_action":"confirm_reservation_info","selected_time":null}',
        ]
    )
    monkeypatch.setattr(
        "services.flow.reservation.hospital.llm_structured.complete_hf_json",
        lambda messages: next(responses),
    )

    result = analyze_hospital_reservation_user_message(
        "confirming_info",
        "네, 맞습니다.",
    )

    assert result["intent"] == "reservation"
    assert result["department"] is None
    assert result["date"] is None
    assert result["time"] is None
    assert result["user_action"] == "confirm_reservation_info"


def test_hospital_structured_analysis_extracts_selected_time(monkeypatch):
    captured_messages = []

    def complete(messages):
        captured_messages.extend(messages)
        return """
        {
          "intent": null,
          "department": null,
          "date": null,
          "time": null,
          "user_name": null,
          "user_action": "select_alternative_time",
          "selected_time": "오후 4시"
        }
        """

    monkeypatch.setattr(
        "services.flow.reservation.hospital.llm_structured.complete_hf_json",
        complete,
    )

    result = analyze_hospital_reservation_user_message(
        "suggest_alternative",
        "오후 4시로 하겠습니다.",
        alternative_times=["오후 4시", "오후 5시"],
    )

    assert result["user_action"] == "select_alternative_time"
    assert result["selected_time"] == "오후 4시"
    assert (
        'available_alternative_times: ["오후 4시", "오후 5시"]' in captured_messages[-1]["content"]
    )


@pytest.mark.parametrize(
    "conversation_state",
    ["reservation_unavailable", "suggest_alternative"],
)
def test_hospital_structured_analysis_retries_noncanonical_alternative_action(
    monkeypatch,
    conversation_state,
):
    responses = iter(
        [
            '{"intent":null,"department":null,"date":null,"time":null,'
            '"user_name":null,"user_action":"continue_collecting",'
            '"selected_time":"오후 4시"}',
            '{"intent":null,"department":null,"date":null,"time":null,'
            '"user_name":null,"user_action":"select_alternative_time",'
            '"selected_time":"오후 4시"}',
        ]
    )
    monkeypatch.setattr(
        "services.flow.reservation.hospital.llm_structured.complete_hf_json",
        lambda messages: next(responses),
    )

    result = analyze_hospital_reservation_user_message(
        conversation_state,
        "오후 4시로 하겠습니다.",
        alternative_times=["오후 4시", "오후 5시"],
    )

    assert result["user_action"] == "select_alternative_time"
    assert result["selected_time"] == "오후 4시"


@pytest.mark.parametrize(
    "conversation_state",
    ["reservation_unavailable", "suggest_alternative"],
)
def test_hospital_structured_analysis_rejects_repeated_noncanonical_alternative_action(
    monkeypatch,
    conversation_state,
):
    monkeypatch.setattr(
        "services.flow.reservation.hospital.llm_structured.complete_hf_json",
        lambda messages: (
            '{"intent":null,"department":null,"date":null,"time":null,'
            '"user_name":null,"user_action":"continue_collecting",'
            '"selected_time":"오후 4시"}'
        ),
    )

    with pytest.raises(AIResponseValidationError):
        analyze_hospital_reservation_user_message(
            conversation_state,
            "오후 4시로 하겠습니다.",
            alternative_times=["오후 4시", "오후 5시"],
        )


@pytest.mark.parametrize(
    ("invalid_action", "invalid_selected_time"),
    [
        ("unknown", "오후 4시"),
        ("select_alternative_time", None),
        ("select_alternative_time", "오후 9시"),
        ("select_alternative_time", "오 후 4 시"),
    ],
)
@pytest.mark.parametrize(
    "conversation_state",
    ["reservation_unavailable", "suggest_alternative"],
)
def test_hospital_structured_analysis_retries_inconsistent_alternative_selection(
    monkeypatch,
    conversation_state,
    invalid_action,
    invalid_selected_time,
):
    invalid_selected_time_json = (
        "null" if invalid_selected_time is None else f'"{invalid_selected_time}"'
    )
    responses = iter(
        [
            '{"intent":null,"department":null,"date":null,"time":null,'
            f'"user_name":null,"user_action":"{invalid_action}",'
            f'"selected_time":{invalid_selected_time_json}}}',
            '{"intent":null,"department":null,"date":null,"time":null,'
            '"user_name":null,"user_action":"select_alternative_time",'
            '"selected_time":"오후 4시"}',
        ]
    )
    monkeypatch.setattr(
        "services.flow.reservation.hospital.llm_structured.complete_hf_json",
        lambda messages: next(responses),
    )

    result = analyze_hospital_reservation_user_message(
        conversation_state,
        "오후 4시로 하겠습니다.",
        alternative_times=["오후 4시", "오후 5시"],
    )

    assert result["user_action"] == "select_alternative_time"
    assert result["selected_time"] == "오후 4시"


@pytest.mark.parametrize(
    ("invalid_action", "invalid_selected_time"),
    [
        ("unknown", "오후 4시"),
        ("select_alternative_time", None),
        ("select_alternative_time", "오후 9시"),
        ("select_alternative_time", "오 후 4 시"),
    ],
)
@pytest.mark.parametrize(
    "conversation_state",
    ["reservation_unavailable", "suggest_alternative"],
)
def test_hospital_structured_analysis_rejects_repeated_inconsistent_selection(
    monkeypatch,
    conversation_state,
    invalid_action,
    invalid_selected_time,
):
    invalid_selected_time_json = (
        "null" if invalid_selected_time is None else f'"{invalid_selected_time}"'
    )
    monkeypatch.setattr(
        "services.flow.reservation.hospital.llm_structured.complete_hf_json",
        lambda messages: (
            '{"intent":null,"department":null,"date":null,"time":null,'
            f'"user_name":null,"user_action":"{invalid_action}",'
            f'"selected_time":{invalid_selected_time_json}}}'
        ),
    )

    with pytest.raises(AIResponseValidationError):
        analyze_hospital_reservation_user_message(
            conversation_state,
            "오후 4시로 하겠습니다.",
            alternative_times=["오후 4시", "오후 5시"],
        )


def test_hospital_structured_analysis_rejects_selected_time_outside_alternative_state(
    monkeypatch,
):
    monkeypatch.setattr(
        "services.flow.reservation.hospital.llm_structured.complete_hf_json",
        lambda messages: (
            '{"intent":"reservation","department":null,"date":null,"time":null,'
            '"user_name":null,"user_action":"continue_collecting",'
            '"selected_time":"오후 4시"}'
        ),
    )

    with pytest.raises(AIResponseValidationError):
        analyze_hospital_reservation_user_message(
            "greeting",
            "병원 예약을 하고 싶어요.",
        )


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
        lambda messages: (
            """
        {
          "intent": "reservation",
          "department": "내과",
          "date": "내일",
          "time": "오후 3시",
          "user_name": "김개굴",
          "user_action": "invalid_action",
          "selected_time": null
        }
        """
        ),
    )

    with pytest.raises(AIResponseValidationError):
        analyze_hospital_reservation_user_message(
            "greeting", "내일 오후 3시에 내과 예약하고 싶습니다."
        )
