from services.flow.professor.assignment.llm_structured import (
    analyze_professor_assignment_user_message,
)


def test_professor_assignment_structured_analysis_extracts_full_info(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.assignment.llm_structured.complete_hf_messages",
        lambda messages: """
        {
          "intent": "assignment_inquiry",
          "assignment_topic": "제출 형식",
          "question": "과제 제출 형식을 여쭤보고 싶습니다.",
          "user_name": "김개굴",
          "user_action": "provide_assignment_info"
        }
        """,
    )

    result = analyze_professor_assignment_user_message(
        "greeting",
        "김개굴 학생입니다. 과제 제출 형식을 여쭤보고 싶습니다.",
    )

    assert result["intent"] == "assignment_inquiry"
    assert result["assignment_topic"] == "제출 형식"
    assert result["question"] == "과제 제출 형식을 여쭤보고 싶습니다."
    assert result["user_name"] == "김개굴"
    assert result["user_action"] == "provide_assignment_info"


def test_professor_assignment_structured_analysis_handles_markdown_json(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.assignment.llm_structured.complete_hf_messages",
        lambda messages: """
        ```json
        {
          "intent": "assignment_inquiry",
          "assignment_topic": "제출 기한",
          "question": "제출 기한을 확인하고 싶습니다.",
          "user_name": null,
          "user_action": "provide_assignment_info"
        }
        ```
        """,
    )

    result = analyze_professor_assignment_user_message(
        "greeting",
        "과제 제출 기한을 확인하고 싶습니다.",
    )

    assert result["assignment_topic"] == "제출 기한"
    assert result["question"] == "제출 기한을 확인하고 싶습니다."
    assert result["user_name"] is None
    assert result["user_action"] == "provide_assignment_info"


def test_professor_assignment_structured_analysis_fallbacks_on_invalid_json(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.assignment.llm_structured.complete_hf_messages",
        lambda messages: "과제 문의로 보입니다.",
    )

    result = analyze_professor_assignment_user_message(
        "greeting",
        "과제 문의드리고 싶습니다.",
    )

    assert result["intent"] == "assignment_inquiry"
    assert result["assignment_topic"] is None
    assert result["question"] is None
    assert result["user_name"] is None
    assert result["user_action"] == "unknown"


def test_professor_assignment_structured_analysis_normalizes_invalid_action(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.assignment.llm_structured.complete_hf_messages",
        lambda messages: """
        {
          "intent": "assignment_inquiry",
          "assignment_topic": "보고서",
          "question": "보고서 분량을 여쭤보고 싶습니다.",
          "user_name": "김개굴",
          "user_action": "invalid_action"
        }
        """,
    )

    result = analyze_professor_assignment_user_message(
        "greeting",
        "김개굴 학생입니다. 보고서 분량을 여쭤보고 싶습니다.",
    )

    assert result["assignment_topic"] == "보고서"
    assert result["question"] == "보고서 분량을 여쭤보고 싶습니다."
    assert result["user_name"] == "김개굴"
    assert result["user_action"] == "unknown"
