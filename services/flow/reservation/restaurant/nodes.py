from __future__ import annotations

from typing import Dict

from services.flow.reservation.restaurant.state import RestaurantReservationState
from services.flow.reservation.restaurant.extractor import extract_restaurant_reservation_info
from services.flow.reservation.restaurant.policy import (
    decide_restaurant_next_state,
    get_missing_restaurant_fields,
)
from services.flow.reservation.restaurant.replies import get_restaurant_recommended_replies
from services.flow.reservation.restaurant.templates import build_restaurant_template_message
from services.flow.reservation.restaurant.availability import resolve_restaurant_availability


def extract_restaurant_info_node(state: RestaurantReservationState) -> Dict:
    """
    사용자 발화에서 식당 예약에 필요한 정보를 추출한다.

    한 번에 모든 정보를 말하지 않는 사용자를 고려해서,
    새로 추출된 값만 갱신하고 기존 값은 유지한다.
    """
    user_message = state.get("user_message", "") or ""
    extracted = extract_restaurant_reservation_info(user_message)

    return {
        "intent": extracted.get("intent") or state.get("intent") or "reservation",
        "service_name": state.get("service_name") or "마음식당",
        "date": extracted.get("date") or state.get("date"),
        "time": extracted.get("time") or state.get("time"),
        "party_size": extracted.get("party_size") or state.get("party_size"),
        "user_name": extracted.get("user_name") or state.get("user_name"),
        "last_ai_message": state.get("last_ai_message"),
        "history": state.get("history") or [],
        "recommended_replies": state.get("recommended_replies") or [],
        "should_end_call": state.get("should_end_call", False),
    }


def decide_restaurant_state_node(state: RestaurantReservationState) -> Dict:
    """
    현재까지 모인 정보를 보고 다음 상태를 결정한다.
    """
    next_state = decide_restaurant_next_state(state)

    return {
        "conversation_state": next_state,
    }


def generate_restaurant_response_node(state: RestaurantReservationState) -> Dict:
    """
    식당 예약 응답을 생성한다.

    콜 포비아 사용자를 고려해서 부족한 정보를 하나씩 딱딱하게 묻기보다,
    부족한 정보를 자연스럽게 묶어서 요청한다.
    """
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"

    if conversation_state == "collecting_reservation_info":
        ai_message = _build_collecting_info_message(state)
    elif conversation_state == "asking_user_name":
        ai_message = _build_asking_user_name_message(state)
    else:
        ai_message = build_restaurant_template_message(conversation_state, state)

    return {
        "ai_message": ai_message,
        "last_ai_message": ai_message,
    }


def attach_restaurant_recommended_replies_node(state: RestaurantReservationState) -> Dict:
    """
    현재 상태에 맞는 추천 답변을 붙인다.
    """
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"

    return {
        "recommended_replies": get_restaurant_recommended_replies(conversation_state),
    }


def _build_collecting_info_message(state: RestaurantReservationState) -> str:
    """
    부족한 예약 정보를 자연스럽게 묶어서 묻는다.
    """
    missing_fields = get_missing_restaurant_fields(state)
    service_name = state.get("service_name") or "마음식당"

    date = state.get("date")
    time = state.get("time")
    party_size = state.get("party_size")
    user_name = state.get("user_name")

    known_parts = []
    if date:
        known_parts.append(date)
    if time:
        known_parts.append(time)
    if party_size:
        known_parts.append(party_size)
    if user_name:
        known_parts.append(f"{user_name}님")

    known_text = " ".join(known_parts)

    if set(missing_fields) == {"date", "time", "party_size", "user_name"}:
        return (
            f"네, {service_name}입니다. 예약 도와드리겠습니다. "
            "예약하실 날짜, 시간, 인원, 예약자 성함을 편하게 말씀해주시겠어요?"
        )

    if "date" in missing_fields and "time" in missing_fields and "party_size" in missing_fields:
        return "네, 예약자 성함은 확인했습니다. 날짜, 시간, 인원은 어떻게 도와드릴까요?"

    if "date" in missing_fields and "time" in missing_fields:
        return f"{known_text} 예약으로 확인했습니다. 방문 날짜와 시간은 언제가 괜찮으세요?"

    if "time" in missing_fields and "party_size" in missing_fields:
        return f"{known_text} 예약으로 확인했습니다. 시간과 인원은 어떻게 도와드릴까요?"

    if "date" in missing_fields and "party_size" in missing_fields:
        return f"{known_text} 예약으로 확인했습니다. 방문 날짜와 인원도 말씀해주시겠어요?"

    if "party_size" in missing_fields and "user_name" in missing_fields:
        return f"{known_text} 예약 가능합니다. 몇 분이서 오시는지와 예약자 성함을 말씀해주시겠어요?"

    if "date" in missing_fields:
        return f"{known_text} 예약으로 확인했습니다. 방문 날짜는 언제가 괜찮으세요?"

    if "time" in missing_fields:
        return f"{known_text} 예약으로 확인했습니다. 시간은 몇 시쯤 괜찮으세요?"

    if "party_size" in missing_fields:
        return f"{known_text} 예약으로 확인했습니다. 몇 분이서 오시나요?"

    if "user_name" in missing_fields:
        return _build_asking_user_name_message(state)

    return build_restaurant_template_message("confirming_info", state)


def _build_asking_user_name_message(state: RestaurantReservationState) -> str:
    """
    예약자 이름만 부족할 때 묻는다.
    """
    date = state.get("date") or "예약 날짜"
    time = state.get("time") or "예약 시간"
    party_size = state.get("party_size") or "인원"

    return f"{date} {time}에 {party_size} 예약으로 확인했습니다. 예약자 성함은 어떻게 남겨드릴까요?"


def check_restaurant_availability_node(state: RestaurantReservationState) -> Dict:
    """
    식당 예약 가능 여부를 확인한다.
    """
    result = resolve_restaurant_availability(state)

    return {
        "availability_status": result.get("availability_status"),
        "availability_reason": result.get("availability_reason"),
        "available_time": result.get("available_time"),
        "alternative_times": result.get("alternative_times") or [],
        "availability_message_hint": result.get("availability_message_hint"),
        "reservation_confirmed": result.get("reservation_confirmed"),
        "simulation_result": result.get("simulation_result"),
    }
