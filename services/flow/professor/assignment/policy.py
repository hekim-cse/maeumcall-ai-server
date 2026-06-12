from __future__ import annotations

from typing import Dict


def compact_professor_assignment_state(result: Dict) -> Dict:
    """
    클라이언트에 저장할 교수님 과제 문의 상태만 정리한다.
    """
    return {
        "intent": result.get("intent"),
        "professor_name": result.get("professor_name"),
        "assignment_topic": result.get("assignment_topic"),
        "question": result.get("question"),
        "user_name": result.get("user_name"),
        "conversation_state": result.get("conversation_state"),
        "missing_fields": result.get("missing_fields") or [],
        "last_ai_message": result.get("ai_message"),
        "user_action": result.get("user_action"),
        "simulation_result": result.get("simulation_result"),
    }
