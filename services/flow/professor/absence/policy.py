from __future__ import annotations

from typing import Dict


def compact_professor_absence_state(result: Dict) -> Dict:
    """
    클라이언트에 저장할 교수님 결석 사유 전달 상태만 정리한다.
    """
    return {
        "intent": result.get("intent"),
        "professor_name": result.get("professor_name"),
        "class_name": result.get("class_name"),
        "absence_date": result.get("absence_date"),
        "absence_reason": result.get("absence_reason"),
        "user_name": result.get("user_name"),
        "conversation_state": result.get("conversation_state"),
        "missing_fields": result.get("missing_fields") or [],
        "last_ai_message": result.get("ai_message"),
        "user_action": result.get("user_action"),
        "simulation_result": result.get("simulation_result"),
    }
