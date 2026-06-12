from services.flow.professor.absence.action_parser import (
    parse_professor_absence_action,
)


def test_confirming_absence_info_confirm_action():
    result = parse_professor_absence_action(
        "confirming_absence_info",
        "네, 맞습니다.",
    )

    assert result["user_action"] == "confirm_absence_info"


def test_confirming_absence_info_change_date_action():
    result = parse_professor_absence_action(
        "confirming_absence_info",
        "결석 날짜를 수정하고 싶습니다.",
    )

    assert result["user_action"] == "change_absence_date"


def test_confirming_absence_info_change_reason_action():
    result = parse_professor_absence_action(
        "confirming_absence_info",
        "결석 사유를 다시 말씀드리겠습니다.",
    )

    assert result["user_action"] == "change_absence_reason"


def test_confirming_absence_info_change_user_name_action():
    result = parse_professor_absence_action(
        "confirming_absence_info",
        "이름을 수정하고 싶습니다.",
    )

    assert result["user_action"] == "change_user_name"


def test_absence_noted_go_closing_action():
    result = parse_professor_absence_action(
        "absence_noted",
        "네, 감사합니다.",
    )

    assert result["user_action"] == "go_closing"


def test_closing_end_call_action():
    result = parse_professor_absence_action(
        "closing",
        "네, 감사합니다.",
    )

    assert result["user_action"] == "end_call"
