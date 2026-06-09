from services.flow.professor.appointment.action_parser import (
    parse_professor_appointment_action,
)


def test_confirming_info_confirm_action():
    result = parse_professor_appointment_action(
        "confirming_info",
        "네, 맞습니다.",
    )

    assert result["user_action"] == "confirm"


def test_confirming_info_change_purpose_action():
    result = parse_professor_appointment_action(
        "confirming_info",
        "면담 목적을 다시 말씀드리고 싶습니다.",
    )

    assert result["user_action"] == "change_appointment_purpose"


def test_confirming_info_change_date_action():
    result = parse_professor_appointment_action(
        "confirming_info",
        "날짜를 변경하고 싶습니다.",
    )

    assert result["user_action"] == "change_date"


def test_confirming_info_change_time_action():
    result = parse_professor_appointment_action(
        "confirming_info",
        "시간을 변경하고 싶습니다.",
    )

    assert result["user_action"] == "change_time"


def test_confirming_info_change_user_name_action():
    result = parse_professor_appointment_action(
        "confirming_info",
        "이름을 수정하고 싶습니다.",
    )

    assert result["user_action"] == "change_user_name"


def test_appointment_confirmed_go_closing_action():
    result = parse_professor_appointment_action(
        "appointment_confirmed",
        "네, 감사합니다.",
    )

    assert result["user_action"] == "go_closing"


def test_closing_end_call_action():
    result = parse_professor_appointment_action(
        "closing",
        "네, 감사합니다.",
    )

    assert result["user_action"] == "end_call"
