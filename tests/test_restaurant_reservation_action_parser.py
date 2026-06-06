from services.flow.reservation.restaurant.action_parser import (
    parse_restaurant_reservation_action,
)


def test_confirming_info_confirm_action():
    result = parse_restaurant_reservation_action(
        "confirming_info",
        "네, 맞습니다.",
    )

    assert result["user_action"] == "confirm"


def test_confirming_info_change_time_action():
    result = parse_restaurant_reservation_action(
        "confirming_info",
        "시간을 바꾸고 싶어요.",
    )

    assert result["user_action"] == "change_time"


def test_confirming_info_change_date_action():
    result = parse_restaurant_reservation_action(
        "confirming_info",
        "날짜를 다시 정하고 싶어요.",
    )

    assert result["user_action"] == "change_date"


def test_confirming_info_change_party_size_action():
    result = parse_restaurant_reservation_action(
        "confirming_info",
        "인원을 바꾸고 싶어요.",
    )

    assert result["user_action"] == "change_party_size"


def test_confirming_info_change_user_name_action():
    result = parse_restaurant_reservation_action(
        "confirming_info",
        "예약자 이름을 바꾸고 싶어요.",
    )

    assert result["user_action"] == "change_user_name"


def test_reservation_available_confirm_action():
    result = parse_restaurant_reservation_action(
        "reservation_available",
        "네, 그 시간으로 예약해주세요.",
    )

    assert result["user_action"] == "confirm_reservation"


def test_reservation_available_ask_other_time_action():
    result = parse_restaurant_reservation_action(
        "reservation_available",
        "그 시간 말고 다른 시간 가능할까요?",
    )

    assert result["user_action"] == "ask_other_time"


def test_reservation_unavailable_ask_other_time_action():
    result = parse_restaurant_reservation_action(
        "reservation_unavailable",
        "다른 시간은 가능할까요?",
    )

    assert result["user_action"] == "ask_other_time"


def test_reservation_unavailable_change_date_action():
    result = parse_restaurant_reservation_action(
        "reservation_unavailable",
        "다른 날짜로 확인해주세요.",
    )

    assert result["user_action"] == "change_date"


def test_reservation_confirmed_go_closing_action():
    result = parse_restaurant_reservation_action(
        "reservation_confirmed",
        "네, 감사합니다.",
    )

    assert result["user_action"] == "go_closing"


def test_closing_end_call_action():
    result = parse_restaurant_reservation_action(
        "closing",
        "네, 괜찮습니다.",
    )

    assert result["user_action"] == "end_call"
