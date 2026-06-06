from __future__ import annotations

from typing import Dict


def compact_hair_salon_state(result: Dict) -> Dict:
    """
    클라이언트에 저장할 미용실 예약 상태만 정리한다.
    """
    return {
        "intent": result.get("intent"),
        "service_name": result.get("service_name"),
        "date": result.get("date"),
        "time": result.get("time"),
        "service_type": result.get("service_type"),
        "user_name": result.get("user_name"),
        "conversation_state": result.get("conversation_state"),
        "last_ai_message": result.get("ai_message"),
        "user_action": result.get("user_action"),
        "selected_time": result.get("selected_time"),
        "availability_status": result.get("availability_status"),
        "availability_reason": result.get("availability_reason"),
        "available_time": result.get("available_time"),
        "alternative_times": result.get("alternative_times") or [],
        "availability_message_hint": result.get("availability_message_hint"),
        "reservation_confirmed": result.get("reservation_confirmed"),
        "simulation_result": result.get("simulation_result"),
    }
