from __future__ import annotations

from typing import Dict, List

from services.flow.reservation.study_room.state import StudyRoomReservationState



def get_missing_study_room_fields(state: StudyRoomReservationState) -> List[str]:
    """
    스터디룸 예약에 필요한 필수 정보 중 아직 없는 값을 반환한다.

    필수 정보:
    - date: 이용 날짜
    - start_time: 시작 시간
    - duration: 이용 시간
    - party_size: 이용 인원
    - user_name: 예약자 이름
    """
    missing_fields = []

    if not state.get("date"):
        missing_fields.append("date")

    if not state.get("start_time"):
        missing_fields.append("start_time")

    if not state.get("duration"):
        missing_fields.append("duration")

    if not state.get("party_size"):
        missing_fields.append("party_size")

    if not state.get("user_name"):
        missing_fields.append("user_name")

    return missing_fields


def compact_study_room_state(result: Dict) -> Dict:
    """
    클라이언트에 저장할 스터디룸 예약 상태만 정리한다.
    """
    return {
        "intent": result.get("intent"),
        "service_name": result.get("service_name"),
        "date": result.get("date"),
        "start_time": result.get("start_time"),
        "duration": result.get("duration"),
        "party_size": result.get("party_size"),
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
