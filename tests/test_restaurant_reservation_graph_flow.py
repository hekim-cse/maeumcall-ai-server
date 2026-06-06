from services.flow.reservation.restaurant.graph import restaurant_reservation_graph


def test_restaurant_reservation_full_info_moves_to_confirming_info():
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


def test_restaurant_reservation_confirm_checks_availability_unavailable():
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


def test_restaurant_reservation_available_confirm_completes_reservation():
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


def test_restaurant_reservation_unavailable_selects_alternative_time():
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


def test_restaurant_reservation_confirmed_moves_to_closing():
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


def test_restaurant_reservation_closing_moves_to_end():
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
