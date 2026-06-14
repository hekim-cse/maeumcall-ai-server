from services.flow.reservation.study_room.llm_structured import (
    analyze_study_room_reservation_user_message,
)


def test_study_room_structured_analysis_extracts_full_info(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.study_room.llm_structured.complete_hf_messages",
        lambda messages: """
        {
          "intent": "reservation",
          "date": "내일",
          "start_time": "오후 2시",
          "duration": "2시간",
          "party_size": "4명",
          "user_name": "김개굴",
          "user_action": "continue_collecting",
          "selected_time": null
        }
        """,
    )

    result = analyze_study_room_reservation_user_message(
        "greeting",
        "내일 오후 2시부터 2시간, 4명 김개굴 이름으로 예약하고 싶습니다.",
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "내일"
    assert result["start_time"] == "오후 2시"
    assert result["duration"] == "2시간"
    assert result["party_size"] == "4명"
    assert result["user_name"] == "김개굴"
    assert result["user_action"] == "continue_collecting"
    assert result["selected_time"] is None


def test_study_room_structured_analysis_handles_markdown_json(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.study_room.llm_structured.complete_hf_messages",
        lambda messages: """
        ```json
        {
          "intent": "reservation",
          "date": "이번 주말",
          "start_time": "오전 10시",
          "duration": "3시간",
          "party_size": "2명",
          "user_name": null,
          "user_action": "continue_collecting",
          "selected_time": null
        }
        ```
        """,
    )

    result = analyze_study_room_reservation_user_message(
        "greeting",
        "이번 주말 오전 10시부터 3시간 2명 예약하고 싶습니다.",
    )

    assert result["date"] == "이번 주말"
    assert result["start_time"] == "오전 10시"
    assert result["duration"] == "3시간"
    assert result["party_size"] == "2명"
    assert result["user_name"] is None


def test_study_room_structured_analysis_extracts_selected_time(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.study_room.llm_structured.complete_hf_messages",
        lambda messages: """
        {
          "intent": "reservation",
          "date": null,
          "start_time": null,
          "duration": null,
          "party_size": null,
          "user_name": null,
          "user_action": "select_alternative_time",
          "selected_time": "오후 3시"
        }
        """,
    )

    result = analyze_study_room_reservation_user_message(
        "reservation_unavailable",
        "오후 3시로 할게요.",
    )

    assert result["user_action"] == "select_alternative_time"
    assert result["selected_time"] == "오후 3시"


def test_study_room_structured_analysis_fallbacks_on_invalid_json(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.study_room.llm_structured.complete_hf_messages",
        lambda messages: "스터디룸 예약으로 보입니다.",
    )

    result = analyze_study_room_reservation_user_message(
        "greeting",
        "스터디룸 예약하고 싶습니다.",
    )

    assert result["intent"] == "reservation"
    assert result["date"] is None
    assert result["start_time"] is None
    assert result["duration"] is None
    assert result["party_size"] is None
    assert result["user_name"] is None
    assert result["user_action"] == "unknown"
    assert result["selected_time"] is None


def test_study_room_structured_analysis_normalizes_invalid_action(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.study_room.llm_structured.complete_hf_messages",
        lambda messages: """
        {
          "intent": "reservation",
          "date": "내일",
          "start_time": "오후 2시",
          "duration": "2시간",
          "party_size": "4명",
          "user_name": "김개굴",
          "user_action": "invalid_action",
          "selected_time": null
        }
        """,
    )

    result = analyze_study_room_reservation_user_message(
        "greeting",
        "내일 오후 2시부터 2시간 4명 예약하고 싶습니다.",
    )

    assert result["date"] == "내일"
    assert result["start_time"] == "오후 2시"
    assert result["duration"] == "2시간"
    assert result["party_size"] == "4명"
    assert result["user_name"] == "김개굴"
    assert result["user_action"] == "unknown"
