from __future__ import annotations

from typing import Dict, List


def get_missing_professor_assignment_fields(state: Dict) -> List[str]:
    """
    교수님 과제 문의에 필요한 필수 정보 중 아직 없는 값을 반환한다.

    필수 정보:
    - course_name: 수업명 또는 과목명
    - assignment_topic: 과제 주제/유형
    - question: 질문 내용
    - user_name: 학생 이름
    """
    missing_fields = []

    if not state.get("course_name"):
        missing_fields.append("course_name")

    if not state.get("assignment_topic"):
        missing_fields.append("assignment_topic")

    if not state.get("question"):
        missing_fields.append("question")

    if not state.get("user_name"):
        missing_fields.append("user_name")

    return missing_fields


def compact_professor_assignment_state(result: Dict) -> Dict:
    """
    클라이언트에 저장할 교수님 과제 문의 상태만 정리한다.
    """
    return {
        "intent": result.get("intent"),
        "professor_name": result.get("professor_name"),
        "course_name": result.get("course_name"),
        "assignment_topic": result.get("assignment_topic"),
        "question": result.get("question"),
        "user_name": result.get("user_name"),
        "conversation_state": result.get("conversation_state"),
        "missing_fields": result.get("missing_fields") or [],
        "last_ai_message": result.get("ai_message"),
        "user_action": result.get("user_action"),
    }
