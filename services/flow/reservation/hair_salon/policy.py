from __future__ import annotations

from typing import Dict, List

from services.flow.reservation.hair_salon.state import HairSalonReservationState


def get_missing_hair_salon_fields(state: HairSalonReservationState) -> List[str]:
    """
    미용실 예약에 필요한 필수 정보 중 아직 없는 값을 반환한다.

    필수 정보:
    - date: 예약 날짜
    - time: 예약 시간
    - service_type: 시술 종류
    - designer: 디자이너
    - user_name: 예약자 이름
    """
    missing_fields: List[str] = []

    if not state.get("date"):
        missing_fields.append("date")

    if not state.get("time"):
        missing_fields.append("time")

    if not state.get("service_type"):
        missing_fields.append("service_type")

    if not state.get("designer"):
        missing_fields.append("designer")

    if not state.get("user_name"):
        missing_fields.append("user_name")

    return missing_fields


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
        "designer": result.get("designer"),
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
    }
