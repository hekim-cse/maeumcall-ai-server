import pytest

from llm.errors import AIResponseValidationError
from services.flow.professor.assignment.llm_structured import (
    analyze_professor_assignment_user_message,
)

pytestmark = pytest.mark.unit


def test_professor_assignment_structured_analysis_extracts_full_info(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.assignment.llm_structured.complete_hf_json",
        lambda messages: (
            """
        {
          "intent": "assignment_inquiry",
          "course_name": "자료구조",
          "assignment_topic": "제출 형식",
          "question": "과제 제출 형식을 여쭤보고 싶습니다.",
          "user_name": "김개굴",
          "user_action": "provide_assignment_info"
        }
        """
        ),
    )

    result = analyze_professor_assignment_user_message(
        "greeting",
        "김개굴 학생입니다. 과제 제출 형식을 여쭤보고 싶습니다.",
    )

    assert result["intent"] == "assignment_inquiry"
    assert result["course_name"] == "자료구조"
    assert result["assignment_topic"] == "제출 형식"
    assert result["question"] == "과제 제출 형식을 여쭤보고 싶습니다."
    assert result["user_name"] == "김개굴"
    assert result["user_action"] == "provide_assignment_info"


def test_professor_assignment_structured_analysis_handles_markdown_json(monkeypatch):
    responses = iter(
        [
            """```json
        {"intent":"assignment_inquiry"}
        ```""",
            '{"intent":"assignment_inquiry","course_name":"자료구조","assignment_topic":"제출 기한","question":"제출 기한을 확인하고 싶습니다.","user_name":null,"user_action":"provide_assignment_info"}',
        ]
    )
    monkeypatch.setattr(
        "services.flow.professor.assignment.llm_structured.complete_hf_json",
        lambda messages: next(responses),
    )

    result = analyze_professor_assignment_user_message(
        "greeting",
        "과제 제출 기한을 확인하고 싶습니다.",
    )

    assert result["assignment_topic"] == "제출 기한"
    assert result["question"] == "제출 기한을 확인하고 싶습니다."
    assert result["user_name"] is None
    assert result["user_action"] == "provide_assignment_info"


def test_professor_assignment_structured_analysis_rejects_invalid_json_after_retry(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.assignment.llm_structured.complete_hf_json",
        lambda messages: "과제 문의로 보입니다.",
    )

    with pytest.raises(AIResponseValidationError):
        analyze_professor_assignment_user_message("greeting", "과제 문의드리고 싶습니다.")


def test_professor_assignment_structured_analysis_rejects_invalid_action(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.assignment.llm_structured.complete_hf_json",
        lambda messages: (
            """
        {
          "intent": "assignment_inquiry",
          "course_name": "자료구조",
          "assignment_topic": "보고서",
          "question": "보고서 분량을 여쭤보고 싶습니다.",
          "user_name": "김개굴",
          "user_action": "invalid_action"
        }
        """
        ),
    )

    with pytest.raises(AIResponseValidationError):
        analyze_professor_assignment_user_message(
            "greeting", "김개굴 학생입니다. 보고서 분량을 여쭤보고 싶습니다."
        )
