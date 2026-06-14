from services.flow.reservation.restaurant.graph import restaurant_reservation_graph


def _patch_restaurant_analysis(monkeypatch):
    def fake_analyze(conversation_state, user_message):
        if conversation_state in ["greeting", "collecting_reservation_info"]:
            if "김개굴" in user_message and ("오늘" in user_message or "저녁" in user_message):
                return {
                    "intent": "reservation",
                    "date": "오늘",
                    "time": "저녁 6시",
                    "party_size": "2명",
                    "user_name": "김개굴",
                    "user_action": "continue_collecting",
                    "selected_time": None,
                }

            return {
                "intent": "reservation",
                "date": None,
                "time": None,
                "party_size": None,
                "user_name": None,
                "user_action": "continue_collecting",
                "selected_time": None,
            }

        if conversation_state == "confirming_info":
            return {
                "intent": "reservation",
                "date": None,
                "time": None,
                "party_size": None,
                "user_name": None,
                "user_action": "confirm",
                "selected_time": None,
            }

        if conversation_state == "reservation_available":
            return {
                "intent": "reservation",
                "date": None,
                "time": None,
                "party_size": None,
                "user_name": None,
                "user_action": "confirm_reservation",
                "selected_time": None,
            }

        if conversation_state == "reservation_unavailable":
            if "8시" in user_message:
                return {
                    "intent": "reservation",
                    "date": None,
                    "time": None,
                    "party_size": None,
                    "user_name": None,
                    "user_action": "select_alternative_time",
                    "selected_time": "저녁 8시",
                }

            return {
                "intent": "reservation",
                "date": None,
                "time": None,
                "party_size": None,
                "user_name": None,
                "user_action": "unknown",
                "selected_time": None,
            }

        if conversation_state == "reservation_confirmed":
            return {
                "intent": "reservation",
                "date": None,
                "time": None,
                "party_size": None,
                "user_name": None,
                "user_action": "go_closing",
                "selected_time": None,
            }

        if conversation_state == "closing":
            return {
                "intent": "reservation",
                "date": None,
                "time": None,
                "party_size": None,
                "user_name": None,
                "user_action": "end_call",
                "selected_time": None,
            }

        return {
            "intent": "reservation",
            "date": None,
            "time": None,
            "party_size": None,
            "user_name": None,
            "user_action": "unknown",
            "selected_time": None,
        }

    monkeypatch.setattr(
        "services.flow.reservation.restaurant.nodes.analyze_restaurant_reservation_user_message",
        fake_analyze,
    )


def test_restaurant_reservation_full_info_moves_to_confirming_info(monkeypatch):
    _patch_restaurant_analysis(monkeypatch)

    result = restaurant_reservation_graph.invoke(
        {
            "user_message": "오늘 저녁 6시에 두 명 김개굴 이름으로 예약하고 싶어요.",
            "conversation_state": "greeting",
            "service_name": "마음식당",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["date"] == "오늘"
    assert result["time"] == "저녁 6시"
    assert result["party_size"] == "2명"
    assert result["user_name"] == "김개굴"
    assert result["conversation_state"] == "confirming_info"
    assert "맞으실까요" in result["ai_message"] or "확인" in result["ai_message"]


def test_restaurant_reservation_confirm_checks_availability_available():
    result = restaurant_reservation_graph.invoke(
        {
            "user_message": "네, 맞습니다.",
            "conversation_state": "confirming_info",
            "service_name": "마음식당",
            "date": "오늘",
            "time": "저녁 6시",
            "party_size": "2명",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_available"
    assert result["availability_status"] == "available"
    assert result["available_time"] == "저녁 6시"
    assert "가능" in result["ai_message"]


def test_restaurant_reservation_confirm_checks_availability_unavailable(monkeypatch):
    _patch_restaurant_analysis(monkeypatch)

    monkeypatch.setattr(
        "services.flow.reservation.restaurant.nodes.generate_restaurant_ai_message",
        lambda state: {
            "ai_message": "죄송합니다. 요청하신 시간은 예약이 어렵습니다. 저녁 6시나 저녁 8시는 가능합니다.",
            "last_ai_message": "죄송합니다. 요청하신 시간은 예약이 어렵습니다. 저녁 6시나 저녁 8시는 가능합니다.",
        },
    )

    result = restaurant_reservation_graph.invoke(
        {
            "user_message": "네, 맞습니다.",
            "conversation_state": "confirming_info",
            "service_name": "마음식당",
            "date": "오늘",
            "time": "저녁 7시",
            "party_size": "2명",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_unavailable"
    assert result["availability_status"] == "unavailable"
    assert result["alternative_times"] == ["저녁 6시", "저녁 8시"]
    assert any(
        keyword in result["ai_message"]
        for keyword in ["어렵", "어려운", "마감", "불가능"]
    )


def test_restaurant_reservation_available_confirm_completes_reservation(monkeypatch):
    _patch_restaurant_analysis(monkeypatch)

    result = restaurant_reservation_graph.invoke(
        {
            "user_message": "네, 예약해주세요.",
            "conversation_state": "reservation_available",
            "service_name": "마음식당",
            "date": "오늘",
            "time": "저녁 6시",
            "party_size": "2명",
            "user_name": "김개굴",
            "availability_status": "available",
            "available_time": "저녁 6시",
            "alternative_times": [],
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_confirmed"
    assert result["reservation_confirmed"] is True
    assert "예약 완료" in result["ai_message"]


def test_restaurant_reservation_unavailable_selects_alternative_time(monkeypatch):
    _patch_restaurant_analysis(monkeypatch)

    result = restaurant_reservation_graph.invoke(
        {
            "user_message": "저녁 8시로 할게요.",
            "conversation_state": "reservation_unavailable",
            "service_name": "마음식당",
            "date": "오늘",
            "time": "저녁 7시",
            "party_size": "2명",
            "user_name": "김개굴",
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["저녁 6시", "저녁 8시"],
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_available"
    assert result["selected_time"] == "저녁 8시"
    assert result["available_time"] == "저녁 8시"
    assert result["availability_status"] == "available"
    assert "가능" in result["ai_message"]


def test_restaurant_reservation_unavailable_rejects_out_of_option_time():
    result = restaurant_reservation_graph.invoke(
        {
            "user_message": "저녁 9시로 할게요.",
            "conversation_state": "reservation_unavailable",
            "service_name": "마음식당",
            "date": "오늘",
            "time": "저녁 7시",
            "party_size": "2명",
            "user_name": "김개굴",
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["저녁 6시", "저녁 8시"],
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_unavailable"
    assert result.get("selected_time") is None
    assert result["reservation_confirmed"] is not True


def test_restaurant_reservation_confirmed_moves_to_closing(monkeypatch):
    _patch_restaurant_analysis(monkeypatch)

    result = restaurant_reservation_graph.invoke(
        {
            "user_message": "네, 감사합니다.",
            "conversation_state": "reservation_confirmed",
            "service_name": "마음식당",
            "date": "오늘",
            "time": "저녁 6시",
            "party_size": "2명",
            "user_name": "김개굴",
            "reservation_confirmed": True,
            "selected_time": "저녁 6시",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "closing"
    assert result["should_end_call"] is False
    assert "감사" in result["ai_message"] or "방문" in result["ai_message"]


def test_restaurant_reservation_closing_moves_to_end(monkeypatch):
    _patch_restaurant_analysis(monkeypatch)

    result = restaurant_reservation_graph.invoke(
        {
            "user_message": "네, 괜찮습니다.",
            "conversation_state": "closing",
            "service_name": "마음식당",
            "date": "오늘",
            "time": "저녁 6시",
            "party_size": "2명",
            "user_name": "김개굴",
            "reservation_confirmed": True,
            "selected_time": "저녁 6시",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "END"
    assert result["should_end_call"] is True
    assert "감사" in result["ai_message"] or "좋은 하루" in result["ai_message"]

def test_restaurant_reservation_change_date_clears_lookup_fields(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.restaurant.llm_structured.analyze_restaurant_reservation_user_message",
        lambda conversation_state, user_message: {
            "intent": None,
            "date": None,
            "time": None,
            "party_size": None,
            "user_name": None,
            "user_action": "change_date",
            "selected_time": None,
        },
    )

    result = restaurant_reservation_graph.invoke(
        {
            "user_message": "날짜를 바꾸고 싶어요.",
            "conversation_state": "confirming_info",
            "service_name": "마음식당",
            "date": "오늘",
            "time": "저녁 6시",
            "party_size": "2명",
            "user_name": "김개굴",
            "availability_status": "available",
            "available_time": "저녁 6시",
            "alternative_times": [],
            "reservation_confirmed": False,
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "collecting_reservation_info"
    assert result["date"] is None
    assert result["availability_status"] is None
    assert result["availability_reason"] is None
    assert result["available_time"] is None
    assert result["alternative_times"] == []
    assert result["availability_message_hint"] is None
    assert result["reservation_confirmed"] is False


def test_restaurant_reservation_change_user_name_resets_user_name_only(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.restaurant.llm_structured.analyze_restaurant_reservation_user_message",
        lambda conversation_state, user_message: {
            "intent": None,
            "date": None,
            "time": None,
            "party_size": None,
            "user_name": None,
            "user_action": "change_user_name",
            "selected_time": None,
        },
    )

    result = restaurant_reservation_graph.invoke(
        {
            "user_message": "예약자 이름 바꿀게요.",
            "conversation_state": "confirming_info",
            "service_name": "마음식당",
            "date": "오늘",
            "time": "저녁 6시",
            "party_size": "2명",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "collecting_reservation_info"
    assert result["date"] == "오늘"
    assert result["time"] == "저녁 6시"
    assert result["party_size"] == "2명"
    assert result["user_name"] is None


def test_restaurant_reservation_unavailable_unknown_keeps_state(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.restaurant.llm_structured.analyze_restaurant_reservation_user_message",
        lambda conversation_state, user_message: {
            "intent": None,
            "date": None,
            "time": None,
            "party_size": None,
            "user_name": None,
            "user_action": "unknown",
            "selected_time": None,
        },
    )

    result = restaurant_reservation_graph.invoke(
        {
            "user_message": "음...",
            "conversation_state": "reservation_unavailable",
            "service_name": "마음식당",
            "date": "오늘",
            "time": "저녁 7시",
            "party_size": "2명",
            "user_name": "김개굴",
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["저녁 6시", "저녁 8시"],
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_unavailable"
    assert result["selected_time"] is None

