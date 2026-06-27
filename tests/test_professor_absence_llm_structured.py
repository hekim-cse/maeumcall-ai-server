import pytest
from services.flow.professor.absence.llm_structured import (
    analyze_professor_absence_user_message,
)



pytestmark = pytest.mark.unit
def test_professor_absence_structured_analysis_extracts_full_info(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.llm_structured.complete_hf_messages",
        lambda messages: """
        {
          "intent": "absence_notice",
          "class_name": "자료구조",
          "absence_date": "오늘",
          "absence_reason": "몸이 좋지 않음",
          "user_name": "김개굴",
          "user_action": "provide_absence_info"
        }
        """,
    )

    result = analyze_professor_absence_user_message(
        "greeting",
        "김개굴 학생입니다. 오늘 자료구조 수업에 몸이 좋지 않아 결석하게 되었습니다.",
    )

    assert result["intent"] == "absence_notice"
    assert result["class_name"] == "자료구조"
    assert result["absence_date"] == "오늘"
    assert result["absence_reason"] == "몸이 좋지 않음"
    assert result["user_name"] == "김개굴"
    assert result["user_action"] == "provide_absence_info"


def test_professor_absence_structured_analysis_handles_markdown_json(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.llm_structured.complete_hf_messages",
        lambda messages: """
        ```json
        {
          "intent": "absence_notice",
          "class_name": null,
          "absence_date": "내일",
          "absence_reason": "병원 방문",
          "user_name": null,
          "user_action": "provide_absence_info"
        }
        ```
        """,
    )

    result = analyze_professor_absence_user_message(
        "greeting",
        "내일 병원에 가게 되어 결석하게 되었습니다.",
    )

    assert result["class_name"] is None
    assert result["absence_date"] == "내일"
    assert result["absence_reason"] == "병원 방문"
    assert result["user_name"] is None
    assert result["user_action"] == "provide_absence_info"


def test_professor_absence_structured_analysis_fallbacks_on_invalid_json(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.llm_structured.complete_hf_messages",
        lambda messages: "결석 사유 전달로 보입니다.",
    )

    result = analyze_professor_absence_user_message(
        "greeting",
        "결석 사유를 말씀드리려고 연락드렸습니다.",
    )

    assert result["intent"] == "absence_notice"
    assert result["class_name"] is None
    assert result["absence_date"] is None
    assert result["absence_reason"] is None
    assert result["user_name"] is None
    assert result["user_action"] == "unknown"


def test_professor_absence_structured_analysis_normalizes_invalid_action(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.llm_structured.complete_hf_messages",
        lambda messages: """
        {
          "intent": "absence_notice",
          "class_name": "자료구조",
          "absence_date": "오늘",
          "absence_reason": "개인 사정",
          "user_name": "김개굴",
          "user_action": "invalid_action"
        }
        """,
    )

    result = analyze_professor_absence_user_message(
        "greeting",
        "김개굴 학생입니다. 오늘 자료구조 수업에 개인 사정으로 결석하게 되었습니다.",
    )

    assert result["class_name"] == "자료구조"
    assert result["absence_date"] == "오늘"
    assert result["absence_reason"] == "개인 사정"
    assert result["user_name"] == "김개굴"
    assert result["user_action"] == "unknown"
