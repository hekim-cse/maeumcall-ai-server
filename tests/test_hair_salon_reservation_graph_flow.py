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
