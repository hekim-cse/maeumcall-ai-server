from services.flow.professor.assignment.action_parser import (
    parse_professor_assignment_action,
)


def test_answering_assignment_question_go_closing_action():
    result = parse_professor_assignment_action(
        "answering_assignment_question",
        "네, 알겠습니다.",
    )

    assert result["user_action"] == "go_closing"


def test_answering_assignment_question_thanks_go_closing_action():
    result = parse_professor_assignment_action(
        "answering_assignment_question",
        "감사합니다.",
    )

    assert result["user_action"] == "go_closing"


def test_answering_assignment_question_follow_up_action():
    result = parse_professor_assignment_action(
        "answering_assignment_question",
        "추가로 하나 더 여쭤봐도 될까요?",
    )

    assert result["user_action"] == "ask_follow_up"


def test_closing_end_call_action():
    result = parse_professor_assignment_action(
        "closing",
        "네, 감사합니다.",
    )

    assert result["user_action"] == "end_call"
