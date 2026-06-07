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
    assert any(
        keyword in result["ai_message"]
        for keyword in ["맞으실까요", "맞으신가요", "맞", "확인"]
    )


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


def test_study_room_reservation_confirm_checks_availability_available():
    result = study_room_reservation_graph.invoke(
        {
            "user_message": "네, 맞습니다.",
            "conversation_state": "confirming_info",
            "service_name": "마음스터디룸",
            "date": "내일",
            "start_time": "오후 3시",
            "duration": "2시간",
            "party_size": "4명",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_available"
    assert result["availability_status"] == "available"
    assert result["available_time"] == "오후 3시"
    assert "가능" in result["ai_message"]


def test_study_room_reservation_confirm_checks_availability_unavailable():
    result = study_room_reservation_graph.invoke(
        {
            "user_message": "네, 맞습니다.",
            "conversation_state": "confirming_info",
            "service_name": "마음스터디룸",
            "date": "내일",
            "start_time": "오후 2시",
            "duration": "2시간",
            "party_size": "4명",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_unavailable"
    assert result["availability_status"] == "unavailable"
    assert result["alternative_times"] == ["오후 1시", "오후 3시"]
    assert any(
        keyword in result["ai_message"]
        for keyword in ["어렵", "어려운", "마감", "불가능"]
    )


def test_study_room_reservation_available_confirm_completes_reservation():
    result = study_room_reservation_graph.invoke(
        {
            "user_message": "네, 예약해주세요.",
            "conversation_state": "reservation_available",
            "service_name": "마음스터디룸",
            "date": "내일",
            "start_time": "오후 3시",
            "duration": "2시간",
            "party_size": "4명",
            "user_name": "김개굴",
            "availability_status": "available",
            "available_time": "오후 3시",
            "alternative_times": [],
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_confirmed"
    assert result["reservation_confirmed"] is True
    assert "예약" in result["ai_message"]
    assert "완료" in result["ai_message"] or "확정" in result["ai_message"]


def test_study_room_reservation_unavailable_selects_alternative_time():
    result = study_room_reservation_graph.invoke(
        {
            "user_message": "오후 3시로 할게요.",
            "conversation_state": "reservation_unavailable",
            "service_name": "마음스터디룸",
            "date": "내일",
            "start_time": "오후 2시",
            "duration": "2시간",
            "party_size": "4명",
            "user_name": "김개굴",
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["오후 1시", "오후 3시"],
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_available"
    assert result["selected_time"] == "오후 3시"
    assert result["available_time"] == "오후 3시"
    assert result["availability_status"] == "available"
    assert "가능" in result["ai_message"]


def test_study_room_reservation_unavailable_rejects_out_of_option_time():
    result = study_room_reservation_graph.invoke(
        {
            "user_message": "오후 5시로 할게요.",
            "conversation_state": "reservation_unavailable",
            "service_name": "마음스터디룸",
            "date": "내일",
            "start_time": "오후 2시",
            "duration": "2시간",
            "party_size": "4명",
            "user_name": "김개굴",
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["오후 1시", "오후 3시"],
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_unavailable"
    assert result.get("selected_time") is None
    assert result["reservation_confirmed"] is not True


def test_study_room_reservation_confirmed_moves_to_closing():
    result = study_room_reservation_graph.invoke(
        {
            "user_message": "네, 감사합니다.",
            "conversation_state": "reservation_confirmed",
            "service_name": "마음스터디룸",
            "date": "내일",
            "start_time": "오후 3시",
            "duration": "2시간",
            "party_size": "4명",
            "user_name": "김개굴",
            "selected_time": "오후 3시",
            "reservation_confirmed": True,
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "closing"
    assert result["should_end_call"] is False


def test_study_room_reservation_closing_moves_to_end():
    result = study_room_reservation_graph.invoke(
        {
            "user_message": "네, 감사합니다.",
            "conversation_state": "closing",
            "service_name": "마음스터디룸",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "END"
    assert result["should_end_call"] is True
