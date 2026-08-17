from __future__ import annotations

from typing import Dict, List, Optional

from services.flow.reservation.restaurant.state import RestaurantReservationState


REQUIRED_FIELDS = ["date", "time", "party_size", "user_name"]


def get_missing_restaurant_fields(state: RestaurantReservationState) -> List[str]:
    """
    식당 예약에 필요한 필수 정보 중 아직 없는 값을 반환한다.

    식당 예약 필수 정보:
    - date: 예약 날짜
    - time: 예약 시간
    - party_size: 인원
    - user_name: 예약자 이름
    """
    missing_fields = []

    for field in REQUIRED_FIELDS:
        value = state.get(field)
        if not value:
            missing_fields.append(field)

    return missing_fields


def decide_restaurant_next_state(state: RestaurantReservationState) -> str:
    """
    현재 수집된 정보를 기준으로 다음 conversation_state를 결정한다.

    콜 포비아 사용자를 고려해서 무조건 하나씩 묻지 않고,
    비어 있는 정보를 자연스럽게 묶어서 질문할 수 있도록 상태를 단순화한다.
    """
    missing_fields = get_missing_restaurant_fields(state)

    if not missing_fields:
        return "confirming_info"

    if "date" in missing_fields or "time" in missing_fields or "party_size" in missing_fields:
        return "collecting_reservation_info"

    if "user_name" in missing_fields:
        return "asking_user_name"

    return "collecting_reservation_info"


def route_after_restaurant_decide(state: RestaurantReservationState) -> str:
    """
    decide 노드 이후 어떤 노드로 이동할지 결정한다.
    """
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"

    if conversation_state == "confirming_info":
        return "generate_response"

    if conversation_state == "asking_user_name":
        return "generate_response"

    if conversation_state == "collecting_reservation_info":
        return "generate_response"

    return "generate_response"


def compact_restaurant_state(result: Dict) -> Dict:
    """
    클라이언트에 저장할 식당 예약 상태만 정리한다.
    """
    return {
        "intent": result.get("intent"),
        "service_name": result.get("service_name"),
        "date": result.get("date"),
        "time": result.get("time"),
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
    }
