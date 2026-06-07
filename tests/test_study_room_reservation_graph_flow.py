from services.flow.reservation.study_room.graph import study_room_reservation_graph


def test_study_room_reservation_full_info_moves_to_confirming_info():
    result = study_room_reservation_graph.invoke(
        {
            "user_message": "내일 오후 두 시부터 두 시간 4명 김개굴 이름으로 예약하고 싶어요.",
            "conversation_state": "greeting",
            "service_name": "마음스터디룸",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["date"] == "내일"
    assert result["start_time"] == "오후 2시"
    assert result["duration"] == "2시간"
    assert result["party_size"] == "4명"
    assert result["user_name"] == "김개굴"
    assert result["conversation_state"] == "confirming_info"
    assert "맞으실까요" in result["ai_message"] or "확인" in result["ai_message"]


def test_study_room_reservation_missing_user_name_keeps_collecting_info():
    result = study_room_reservation_graph.invoke(
        {
            "user_message": "내일 오후 두 시부터 두 시간 4명 예약 가능할까요?",
            "conversation_state": "greeting",
            "service_name": "마음스터디룸",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["date"] == "내일"
    assert result["start_time"] == "오후 2시"
    assert result["duration"] == "2시간"
    assert result["party_size"] == "4명"
    assert result["user_name"] is None
    assert result["conversation_state"] == "collecting_reservation_info"
    assert "성함" in result["ai_message"]


def test_study_room_reservation_partial_info_is_preserved():
    first = study_room_reservation_graph.invoke(
        {
            "user_message": "내일 오후 두 시부터 두 시간 예약 가능할까요?",
            "conversation_state": "greeting",
            "service_name": "마음스터디룸",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    second = study_room_reservation_graph.invoke(
        {
            **first,
            "user_message": "4명이고 김개굴 이름으로 예약해주세요.",
        }
    )

    assert second["date"] == "내일"
    assert second["start_time"] == "오후 2시"
    assert second["duration"] == "2시간"
    assert second["party_size"] == "4명"
    assert second["user_name"] == "김개굴"
    assert second["conversation_state"] == "confirming_info"
