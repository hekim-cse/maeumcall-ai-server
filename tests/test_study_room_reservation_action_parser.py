from services.flow.reservation.study_room.action_parser import parse_study_room_reservation_action


def test_confirming_info_confirm_action():
    result = parse_study_room_reservation_action(
        "confirming_info",
        "네, 맞습니다.",
    )

    assert result["user_action"] == "confirm"


def test_confirming_info_change_start_time_action():
    result = parse_study_room_reservation_action(
        "confirming_info",
        "시작 시간을 바꾸고 싶어요.",
    )

    assert result["user_action"] == "change_start_time"


def test_confirming_info_change_duration_action():
    result = parse_study_room_reservation_action(
        "confirming_info",
        "이용 시간을 바꾸고 싶어요.",
    )

    assert result["user_action"] == "change_duration"


def test_confirming_info_change_party_size_action():
    result = parse_study_room_reservation_action(
        "confirming_info",
        "인원을 바꾸고 싶어요.",
    )

    assert result["user_action"] == "change_party_size"


def test_confirming_info_change_user_name_action():
    result = parse_study_room_reservation_action(
        "confirming_info",
        "예약자 이름을 바꾸고 싶어요.",
    )

    assert result["user_action"] == "change_user_name"


def test_reservation_available_confirm_action():
    result = parse_study_room_reservation_action(
        "reservation_available",
        "네, 예약해주세요.",
    )

    assert result["user_action"] == "confirm_reservation"


def test_reservation_available_ask_other_time_action():
    result = parse_study_room_reservation_action(
        "reservation_available",
        "그 시간 말고 다른 시간 가능할까요?",
    )

    assert result["user_action"] == "ask_other_time"


def test_reservation_unavailable_select_alternative_time_action():
    result = parse_study_room_reservation_action(
        "reservation_unavailable",
        "오후 3시로 할게요.",
    )

    assert result["user_action"] == "select_alternative_time"
    assert result["selected_time"] == "오후 3시"


def test_reservation_unavailable_ask_other_time_action():
    result = parse_study_room_reservation_action(
        "reservation_unavailable",
        "다른 시간 가능할까요?",
    )

    assert result["user_action"] == "ask_other_time"


def test_reservation_unavailable_change_date_action():
    result = parse_study_room_reservation_action(
        "reservation_unavailable",
        "다른 날짜로 확인해주세요.",
    )

    assert result["user_action"] == "change_date"


def test_reservation_confirmed_go_closing_action():
    result = parse_study_room_reservation_action(
        "reservation_confirmed",
        "네, 감사합니다.",
    )

    assert result["user_action"] == "go_closing"


def test_closing_end_call_action():
    result = parse_study_room_reservation_action(
        "closing",
        "네, 감사합니다.",
    )

    assert result["user_action"] == "end_call"
