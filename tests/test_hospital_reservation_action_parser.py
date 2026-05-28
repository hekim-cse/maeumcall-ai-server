from services.flow.hospital_reservation_action_parser import (
    parse_hospital_reservation_action,
)


def _parse(user_message: str, conversation_state: str, **extra_state):
    state = {
        "user_message": user_message,
        "conversation_state": conversation_state,
        **extra_state,
    }

    return parse_hospital_reservation_action(state)


def test_confirming_info_confirm_action():
    result = _parse(
        user_message="네, 맞습니다.",
        conversation_state="confirming_info",
    )

    assert result["user_action"] == "confirm_reservation_info"
    assert result["selected_time"] is None


def test_confirming_info_change_time_action():
    result = _parse(
        user_message="시간을 바꾸고 싶어요.",
        conversation_state="confirming_info",
    )

    assert result["user_action"] == "change_time"


def test_confirming_info_change_date_action():
    result = _parse(
        user_message="날짜를 다시 정하고 싶어요.",
        conversation_state="confirming_info",
    )

    assert result["user_action"] == "change_date"


def test_confirming_info_change_department_action():
    result = _parse(
        user_message="진료과를 바꿀게요.",
        conversation_state="confirming_info",
    )

    assert result["user_action"] == "change_department"


def test_reservation_available_confirm_time_action():
    result = _parse(
        user_message="네, 그 시간으로 예약하고 싶습니다.",
        conversation_state="reservation_available",
    )

    assert result["user_action"] == "confirm_available_time"


def test_reservation_available_confirm_progress_action():
    result = _parse(
        user_message="그걸로 진행해주세요.",
        conversation_state="reservation_available",
    )

    assert result["user_action"] == "confirm_available_time"


def test_reservation_available_ask_other_time_action():
    result = _parse(
        user_message="다른 시간도 가능할까요?",
        conversation_state="reservation_available",
    )

    assert result["user_action"] == "ask_other_time"


def test_reservation_available_ask_other_time_with_rejection_action():
    result = _parse(
        user_message="그 시간 말고 다른 시간으로요.",
        conversation_state="reservation_available",
    )

    assert result["user_action"] == "ask_other_time"


def test_reservation_unavailable_ask_other_time_action():
    result = _parse(
        user_message="가장 빠른 시간으로 부탁드립니다.",
        conversation_state="reservation_unavailable",
    )

    assert result["user_action"] == "ask_other_time"


def test_reservation_unavailable_when_possible_action():
    result = _parse(
        user_message="언제 가능할까요?",
        conversation_state="reservation_unavailable",
    )

    assert result["user_action"] == "ask_other_time"


def test_suggest_alternative_select_first_time_action():
    result = _parse(
        user_message="오후 4시로 하겠습니다.",
        conversation_state="suggest_alternative",
        alternative_times=["오후 4시", "오후 5시"],
    )

    assert result["user_action"] == "select_alternative_time"
    assert result["selected_time"] == "오후 4시"


def test_suggest_alternative_select_second_time_action():
    result = _parse(
        user_message="오후 5시는 가능할까요?",
        conversation_state="suggest_alternative",
        alternative_times=["오후 4시", "오후 5시"],
    )

    assert result["user_action"] == "select_alternative_time"
    assert result["selected_time"] == "오후 5시"


def test_suggest_alternative_select_out_of_option_time_action():
    result = _parse(
        user_message="오후 7시로 하겠습니다.",
        conversation_state="suggest_alternative",
        alternative_times=["오후 4시", "오후 5시"],
    )

    assert result["user_action"] == "select_alternative_time"
    assert result["selected_time"] == "오후 7시"


def test_suggest_alternative_change_date_action():
    result = _parse(
        user_message="다른 날짜로 확인해주세요.",
        conversation_state="suggest_alternative",
        alternative_times=["오후 4시", "오후 5시"],
    )

    assert result["user_action"] == "change_date"


def test_suggest_alternative_ask_other_time_action():
    result = _parse(
        user_message="다른 시간도 있나요?",
        conversation_state="suggest_alternative",
        alternative_times=["오후 4시", "오후 5시"],
    )

    assert result["user_action"] == "ask_other_time"


def test_reservation_confirmed_go_closing_action():
    result = _parse(
        user_message="네, 감사합니다.",
        conversation_state="reservation_confirmed",
    )

    assert result["user_action"] == "go_closing"


def test_closing_end_call_action():
    result = _parse(
        user_message="네, 감사합니다.",
        conversation_state="closing",
    )

    assert result["user_action"] == "end_call"


def test_checking_availability_lookup_action():
    result = _parse(
        user_message="네, 기다리겠습니다.",
        conversation_state="checking_availability",
    )

    assert result["user_action"] == "lookup_availability"


# =========================
# 2차 보강 테스트 케이스
# =========================

def test_reservation_available_confirm_short_positive_action():
    result = _parse(
        user_message="네 좋아요.",
        conversation_state="reservation_available",
    )

    assert result["user_action"] == "confirm_available_time"


def test_reservation_available_confirm_that_option_action():
    result = _parse(
        user_message="그걸로 해주세요.",
        conversation_state="reservation_available",
    )

    assert result["user_action"] == "confirm_available_time"


def test_reservation_available_reject_and_ask_other_time_action():
    result = _parse(
        user_message="아니요 다른 시간으로 부탁드려요.",
        conversation_state="reservation_available",
    )

    assert result["user_action"] == "ask_other_time"


def test_confirming_info_change_department_to_dermatology_action():
    result = _parse(
        user_message="피부과로 바꿀게요.",
        conversation_state="confirming_info",
    )

    assert result["user_action"] == "change_department"


def test_confirming_info_change_date_tomorrow_to_day_after_action():
    result = _parse(
        user_message="내일 말고 모레로 할게요.",
        conversation_state="confirming_info",
    )

    assert result["user_action"] == "change_date"


def test_suggest_alternative_select_time_short_answer_action():
    result = _parse(
        user_message="오후 4시요.",
        conversation_state="suggest_alternative",
        alternative_times=["오후 4시", "오후 5시"],
    )

    assert result["user_action"] == "select_alternative_time"
    assert result["selected_time"] == "오후 4시"


def test_suggest_alternative_select_time_polite_request_action():
    result = _parse(
        user_message="오후 5시로 부탁드려요.",
        conversation_state="suggest_alternative",
        alternative_times=["오후 4시", "오후 5시"],
    )

    assert result["user_action"] == "select_alternative_time"
    assert result["selected_time"] == "오후 5시"


def test_suggest_alternative_ask_fastest_available_time_action():
    result = _parse(
        user_message="가능한 시간 중 빠른 걸로 부탁드려요.",
        conversation_state="suggest_alternative",
        alternative_times=["오후 4시", "오후 5시"],
    )

    assert result["user_action"] == "ask_other_time"


def test_suggest_alternative_change_date_day_after_tomorrow_action():
    result = _parse(
        user_message="내일 말고 모레로 예약할게요.",
        conversation_state="suggest_alternative",
        alternative_times=["오후 4시", "오후 5시"],
    )

    assert result["user_action"] == "change_date"


def test_reservation_unavailable_change_date_action():
    result = _parse(
        user_message="다른 날짜로 확인해주세요.",
        conversation_state="reservation_unavailable",
    )

    assert result["user_action"] == "change_date"
    assert result["selected_time"] is None
