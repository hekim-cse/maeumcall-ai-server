from services.flow.reservation.hair_salon.graph import hair_salon_reservation_graph


def test_hair_salon_reservation_full_info_moves_to_confirming_info():
    result = hair_salon_reservation_graph.invoke(
        {
            "user_message": "내일 오후 3시에 수진 디자이너님으로 커트 김개굴 이름으로 예약하고 싶어요.",
            "conversation_state": "greeting",
            "service_name": "마음헤어",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["date"] == "내일"
    assert result["time"] == "오후 3시"
    assert result["service_type"] == "커트"
    assert result["designer"] == "수진"
    assert result["user_name"] == "김개굴"
    assert result["conversation_state"] == "confirming_info"
    assert "예약" in result["ai_message"]


def test_hair_salon_reservation_missing_designer_keeps_collecting_info():
    result = hair_salon_reservation_graph.invoke(
        {
            "user_message": "내일 오후 3시에 커트 김개굴 이름으로 예약하고 싶어요.",
            "conversation_state": "greeting",
            "service_name": "마음헤어",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["date"] == "내일"
    assert result["time"] == "오후 3시"
    assert result["service_type"] == "커트"
    assert result["user_name"] == "김개굴"
    assert result["designer"] is None
    assert result["conversation_state"] == "collecting_reservation_info"
    assert "디자이너" in result["ai_message"] or "선생님" in result["ai_message"]


def test_hair_salon_reservation_any_designer_moves_to_confirming_info():
    result = hair_salon_reservation_graph.invoke(
        {
            "user_message": "내일 오후 4시에 아무 선생님이나 커트 김개굴 이름으로 예약하고 싶어요.",
            "conversation_state": "greeting",
            "service_name": "마음헤어",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["date"] == "내일"
    assert result["time"] == "오후 4시"
    assert result["service_type"] == "커트"
    assert result["designer"] == "가능한 디자이너"
    assert result["user_name"] == "김개굴"
    assert result["conversation_state"] == "confirming_info"


def test_hair_salon_reservation_confirm_checks_availability_available():
    result = hair_salon_reservation_graph.invoke(
        {
            "user_message": "네, 맞습니다.",
            "conversation_state": "confirming_info",
            "service_name": "마음헤어",
            "date": "내일",
            "time": "오후 4시",
            "service_type": "커트",
            "designer": "수진",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_available"
    assert result["availability_status"] == "available"
    assert result["available_time"] == "오후 4시"
    assert "가능" in result["ai_message"]


def test_hair_salon_reservation_confirm_checks_availability_unavailable():
    result = hair_salon_reservation_graph.invoke(
        {
            "user_message": "네, 맞습니다.",
            "conversation_state": "confirming_info",
            "service_name": "마음헤어",
            "date": "내일",
            "time": "오후 3시",
            "service_type": "커트",
            "designer": "수진",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_unavailable"
    assert result["availability_status"] == "unavailable"
    assert result["alternative_times"] == ["오후 2시", "오후 4시"]
    assert any(
        keyword in result["ai_message"]
        for keyword in ["어렵", "어려운", "마감", "불가능"]
    )


def test_hair_salon_reservation_available_confirm_completes_reservation():
    result = hair_salon_reservation_graph.invoke(
        {
            "user_message": "네, 예약해주세요.",
            "conversation_state": "reservation_available",
            "service_name": "마음헤어",
            "date": "내일",
            "time": "오후 4시",
            "service_type": "커트",
            "designer": "수진",
            "user_name": "김개굴",
            "availability_status": "available",
            "available_time": "오후 4시",
            "alternative_times": [],
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_confirmed"
    assert result["reservation_confirmed"] is True
    assert "예약" in result["ai_message"]


def test_hair_salon_reservation_unavailable_selects_alternative_time():
    result = hair_salon_reservation_graph.invoke(
        {
            "user_message": "오후 4시로 할게요.",
            "conversation_state": "reservation_unavailable",
            "service_name": "마음헤어",
            "date": "내일",
            "time": "오후 3시",
            "service_type": "커트",
            "designer": "수진",
            "user_name": "김개굴",
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["오후 2시", "오후 4시"],
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_available"
    assert result["selected_time"] == "오후 4시"
    assert result["available_time"] == "오후 4시"
    assert result["availability_status"] == "available"
    assert "가능" in result["ai_message"]


def test_hair_salon_reservation_unavailable_rejects_out_of_option_time():
    result = hair_salon_reservation_graph.invoke(
        {
            "user_message": "오후 6시로 할게요.",
            "conversation_state": "reservation_unavailable",
            "service_name": "마음헤어",
            "date": "내일",
            "time": "오후 3시",
            "service_type": "커트",
            "designer": "수진",
            "user_name": "김개굴",
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["오후 2시", "오후 4시"],
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_unavailable"
    assert result.get("selected_time") is None
    assert result["reservation_confirmed"] is not True


def test_hair_salon_reservation_confirmed_moves_to_closing():
    result = hair_salon_reservation_graph.invoke(
        {
            "user_message": "네, 감사합니다.",
            "conversation_state": "reservation_confirmed",
            "service_name": "마음헤어",
            "date": "내일",
            "time": "오후 4시",
            "service_type": "커트",
            "designer": "수진",
            "user_name": "김개굴",
            "selected_time": "오후 4시",
            "reservation_confirmed": True,
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "closing"
    assert result["should_end_call"] is False


def test_hair_salon_reservation_closing_moves_to_end():
    result = hair_salon_reservation_graph.invoke(
        {
            "user_message": "네, 감사합니다.",
            "conversation_state": "closing",
            "service_name": "마음헤어",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "END"
    assert result["should_end_call"] is True
