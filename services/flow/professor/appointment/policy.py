from __future__ import annotations

from typing import Dict, List


def get_missing_professor_appointment_fields(state: Dict) -> List[str]:
    """
    교수님 면담 예약에 필요한 필수 정보 중 아직 없는 값을 반환한다.

    필수 정보:
    - appointment_purpose: 면담 목적
    - date: 희망 날짜
    - time: 희망 시간
    - user_name: 학생 이름
    """
    missing_fields = []

    if not state.get("appointment_purpose"):
        missing_fields.append("appointment_purpose")

    if not state.get("date"):
        missing_fields.append("date")

    if not state.get("time"):
        missing_fields.append("time")

    if not state.get("user_name"):
        missing_fields.append("user_name")

    return missing_fields


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
        "missing_fields": result.get("missing_fields") or [],
        "last_ai_message": result.get("ai_message"),
        "user_action": result.get("user_action"),
        "simulation_result": result.get("simulation_result"),
    }
