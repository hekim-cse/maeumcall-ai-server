from services.flow.reservation.hair_salon.llm_structured import (
    analyze_hair_salon_reservation_user_message,
)


def test_hair_salon_structured_analysis_extracts_full_info(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.hair_salon.llm_structured.complete_hf_messages",
        lambda messages: """
        {
          "intent": "reservation",
          "date": "내일",
          "time": "오후 2시",
          "service_type": "커트",
          "designer": "수진",
          "user_name": "김개굴",
          "user_action": "continue_collecting",
          "selected_time": null
        }
        """,
    )

    result = analyze_hair_salon_reservation_user_message(
        "greeting",
        "내일 오후 2시에 수진 선생님 커트 김개굴 이름으로 예약하고 싶어요.",
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "내일"
    assert result["time"] == "오후 2시"
    assert result["service_type"] == "커트"
    assert result["designer"] == "수진"
    assert result["user_name"] == "김개굴"
    assert result["user_action"] == "continue_collecting"
    assert result["selected_time"] is None


def test_hair_salon_structured_analysis_handles_markdown_json(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.hair_salon.llm_structured.complete_hf_messages",
        lambda messages: """
        ```json
        {
          "intent": "reservation",
          "date": "모레",
          "time": "저녁 6시",
          "service_type": "펌",
          "designer": "가능한 디자이너",
          "user_name": "김개굴",
          "user_action": "continue_collecting",
          "selected_time": null
        }
        ```
        """,
    )

    result = analyze_hair_salon_reservation_user_message(
        "greeting",
        "모레 저녁 6시에 가능한 선생님으로 펌 예약하고 싶어요.",
    )

    assert result["date"] == "모레"
    assert result["time"] == "저녁 6시"
    assert result["service_type"] == "펌"
    assert result["designer"] == "가능한 디자이너"
    assert result["user_name"] == "김개굴"


def test_hair_salon_structured_analysis_extracts_selected_time(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.hair_salon.llm_structured.complete_hf_messages",
        lambda messages: """
        {
          "intent": "reservation",
          "date": null,
          "time": null,
          "service_type": null,
          "designer": null,
          "user_name": null,
          "user_action": "select_alternative_time",
          "selected_time": "오후 3시"
        }
        """,
    )

    result = analyze_hair_salon_reservation_user_message(
        "reservation_unavailable",
        "오후 3시로 할게요.",
    )

    assert result["user_action"] == "select_alternative_time"
    assert result["selected_time"] == "오후 3시"


def test_hair_salon_structured_analysis_fallbacks_on_invalid_json(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.hair_salon.llm_structured.complete_hf_messages",
        lambda messages: "JSON이 아닙니다.",
    )

    result = analyze_hair_salon_reservation_user_message(
        "greeting",
        "미용실 예약하고 싶습니다.",
    )

    assert result["intent"] == "reservation"
    assert result["date"] is None
    assert result["time"] is None
    assert result["service_type"] is None
    assert result["designer"] is None
    assert result["user_name"] is None
    assert result["user_action"] == "unknown"
    assert result["selected_time"] is None


def test_hair_salon_structured_analysis_normalizes_invalid_action(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.hair_salon.llm_structured.complete_hf_messages",
        lambda messages: """
        {
          "intent": "reservation",
          "date": "내일",
          "time": "오후 2시",
          "service_type": "커트",
          "designer": "수진",
          "user_name": "김개굴",
          "user_action": "invalid_action",
          "selected_time": null
        }
        """,
    )

    result = analyze_hair_salon_reservation_user_message(
        "greeting",
        "내일 오후 2시에 수진 선생님 커트 예약하고 싶습니다.",
    )

    assert result["date"] == "내일"
    assert result["time"] == "오후 2시"
    assert result["service_type"] == "커트"
    assert result["designer"] == "수진"
    assert result["user_name"] == "김개굴"
    assert result["user_action"] == "unknown"
