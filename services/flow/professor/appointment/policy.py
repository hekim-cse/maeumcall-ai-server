from __future__ import annotations

from typing import Dict


def compact_professor_appointment_state(result: Dict) -> Dict:
    """
    클라이언트에 저장할 교수님 면담 예약 상태만 정리한다.
    """
    return {
        "intent": result.get("intent"),
        "professor_name": result.get("professor_name"),
        "appointment_purpose": result.get("appointment_purpose"),
        "date": result.get("date"),
        "time": result.get("time"),
        "user_name": result.get("user_name"),
        "conversation_state": result.get("conversation_state"),
        "last_ai_message": result.get("ai_message"),
        "user_action": result.get("user_action"),
        "simulation_result": result.get("simulation_result"),
    }
