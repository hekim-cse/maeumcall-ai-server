from __future__ import annotations

from typing import Dict

from services.flow.reservation.hair_salon.state import HairSalonReservationState
from services.flow.reservation.hair_salon.extractor import extract_hair_salon_reservation_info
from services.flow.reservation.hair_salon.generation import generate_hair_salon_ai_message
from services.flow.reservation.hair_salon.policy import get_missing_hair_salon_fields
from services.flow.reservation.hair_salon.replies import get_hair_salon_recommended_replies
from services.flow.reservation.hair_salon.action_parser import parse_hair_salon_reservation_action
from services.flow.reservation.hair_salon.availability import resolve_hair_salon_availability


def extract_hair_salon_info_node(state: HairSalonReservationState) -> Dict:
    """
    사용자 발화에서 미용실 예약에 필요한 정보를 추출한다.

    한 번에 모든 정보를 말하지 않는 사용자를 고려해서,
    새로 추출된 값만 갱신하고 기존 값은 유지한다.
    """
    user_message = state.get("user_message", "") or ""
    extracted = extract_hair_salon_reservation_info(user_message)

    return {
        "intent": extracted.get("intent") or state.get("intent") or "reservation",
        "service_name": state.get("service_name") or "마음헤어",
        "date": extracted.get("date") or state.get("date"),
        "time": extracted.get("time") or state.get("time"),
        "service_type": extracted.get("service_type") or state.get("service_type"),
        "designer": extracted.get("designer") or state.get("designer"),
        "user_name": extracted.get("user_name") or state.get("user_name"),
        "last_ai_message": state.get("last_ai_message"),
        "history": state.get("history") or [],
        "recommended_replies": state.get("recommended_replies") or [],
        "should_end_call": state.get("should_end_call", False),
    }


def decide_hair_salon_state_node(state: HairSalonReservationState) -> Dict:
    """
    미용실 예약 상태를 결정한다.

    - 정보가 부족하면 collecting_reservation_info
    - 정보가 모두 모이면 confirming_info
    - 예약 정보 확인 후 가능 여부를 조회한다
    - 가능/불가 안내 후 사용자 응답에 따라 확정 또는 재수집으로 이동한다
    """
    user_message = state.get("user_message", "") or ""
    current_state = state.get("conversation_state") or "greeting"

    action_result = parse_hair_salon_reservation_action(
        current_state,
        user_message,
    )
    user_action = action_result.get("user_action")

    if current_state == "confirming_info":
        if user_action == "confirm":
            return {
                "user_action": user_action,
                "conversation_state": "checking_availability",
            }

        if user_action == "change_date":
            return {
                "user_action": user_action,
                "date": None,
                "availability_status": None,
                "availability_reason": None,
                "available_time": None,
                "alternative_times": [],
                "availability_message_hint": None,
                "reservation_confirmed": False,
                "conversation_state": "collecting_reservation_info",
            }

        if user_action == "change_time":
            return {
                "user_action": user_action,
                "time": None,
                "availability_status": None,
                "availability_reason": None,
                "available_time": None,
                "alternative_times": [],
                "availability_message_hint": None,
                "reservation_confirmed": False,
                "conversation_state": "collecting_reservation_info",
            }

        if user_action == "change_service_type":
            return {
                "user_action": user_action,
                "service_type": None,
                "availability_status": None,
                "availability_reason": None,
                "available_time": None,
                "alternative_times": [],
                "availability_message_hint": None,
                "reservation_confirmed": False,
                "conversation_state": "collecting_reservation_info",
            }

        if user_action == "change_designer":
            return {
                "user_action": user_action,
                "designer": None,
                "availability_status": None,
                "availability_reason": None,
                "available_time": None,
                "alternative_times": [],
                "availability_message_hint": None,
                "reservation_confirmed": False,
                "conversation_state": "collecting_reservation_info",
            }

        if user_action == "change_user_name":
            return {
                "user_action": user_action,
                "user_name": None,
                "reservation_confirmed": False,
                "conversation_state": "collecting_reservation_info",
            }

        return {
            "user_action": user_action,
            "conversation_state": "confirming_info",
        }

    if current_state == "reservation_available":
        if user_action == "confirm_reservation":
            final_time = state.get("available_time") or state.get("selected_time") or state.get("time")

            return {
                "user_action": user_action,
                "selected_time": final_time,
                "reservation_confirmed": True,
                "conversation_state": "reservation_confirmed",
            }

        if user_action == "ask_other_time":
            return {
                "user_action": user_action,
                "time": None,
                "availability_status": None,
                "availability_reason": None,
                "available_time": None,
                "alternative_times": [],
                "availability_message_hint": None,
                "reservation_confirmed": False,
                "conversation_state": "collecting_reservation_info",
            }

        if user_action == "change_date":
            return {
                "user_action": user_action,
                "date": None,
                "time": None,
                "availability_status": None,
                "availability_reason": None,
                "available_time": None,
                "alternative_times": [],
                "availability_message_hint": None,
                "reservation_confirmed": False,
                "conversation_state": "collecting_reservation_info",
            }

        return {
            "user_action": user_action,
            "conversation_state": "reservation_available",
        }

    if current_state == "reservation_unavailable":
        selected_time = action_result.get("selected_time")
        alternative_times = state.get("alternative_times") or []

        if selected_time and selected_time in alternative_times:
            return {
                "user_action": "select_alternative_time",
                "time": selected_time,
                "selected_time": selected_time,
                "available_time": selected_time,
                "availability_status": "available",
                "availability_reason": None,
                "availability_message_hint": f"{state.get('date')} {selected_time}에 {state.get('designer')} 선생님 {state.get('service_type')} 예약이 가능합니다.",
                "reservation_confirmed": False,
                "conversation_state": "reservation_available",
            }

        if selected_time and selected_time not in alternative_times:
            return {
                "user_action": "invalid_alternative_time",
                "reservation_confirmed": False,
                "conversation_state": "reservation_unavailable",
            }

        if user_action == "change_date":
            return {
                "user_action": user_action,
                "date": None,
                "time": None,
                "availability_status": None,
                "availability_reason": None,
                "available_time": None,
                "alternative_times": [],
                "availability_message_hint": None,
                "reservation_confirmed": False,
                "conversation_state": "collecting_reservation_info",
            }

        if user_action == "ask_other_time":
            return {
                "user_action": user_action,
                "time": None,
                "availability_status": None,
                "availability_reason": None,
                "available_time": None,
                "alternative_times": [],
                "availability_message_hint": None,
                "reservation_confirmed": False,
                "conversation_state": "collecting_reservation_info",
            }

        return {
            "user_action": user_action,
            "conversation_state": "reservation_unavailable",
        }

    if current_state == "reservation_confirmed":
        if user_action == "go_closing":
            return {
                "user_action": user_action,
                "conversation_state": "closing",
            }

        return {
            "user_action": user_action,
            "conversation_state": "reservation_confirmed",
        }

    if current_state == "closing":
        if user_action == "end_call":
            return {
                "user_action": user_action,
                "conversation_state": "END",
                "should_end_call": True,
            }

        return {
            "user_action": user_action,
            "conversation_state": "closing",
        }

    missing_fields = get_missing_hair_salon_fields(state)

    if missing_fields:
        return {
            "user_action": user_action,
            "missing_fields": missing_fields,
            "conversation_state": "collecting_reservation_info",
        }

    return {
        "user_action": user_action,
        "missing_fields": [],
        "conversation_state": "confirming_info",
    }


def generate_hair_salon_response_node(state: HairSalonReservationState) -> Dict:
    """
    미용실 예약 응답 생성 노드이다.

    LLM 응답을 우선 사용하고, validator를 통과하지 못하면 template fallback을 사용한다.
    """
    ai_message = generate_hair_salon_ai_message(state)

    return {
        "ai_message": ai_message,
        "last_ai_message": ai_message,
    }


def attach_hair_salon_recommended_replies_node(state: HairSalonReservationState) -> Dict:
    """
    현재 상태에 맞는 추천 답변을 붙인다.
    """
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"

    return {
        "recommended_replies": get_hair_salon_recommended_replies(conversation_state),
    }


def check_hair_salon_availability_node(state: HairSalonReservationState) -> Dict:
    """
    미용실 예약 가능 여부를 확인하는 노드이다.
    """
    result = resolve_hair_salon_availability(state)
    next_state = (
        "reservation_available"
        if result.get("availability_status") == "available"
        else "reservation_unavailable"
    )

    return {
        "availability_status": result.get("availability_status"),
        "availability_reason": result.get("availability_reason"),
        "available_time": result.get("available_time"),
        "alternative_times": result.get("alternative_times") or [],
        "availability_message_hint": result.get("availability_message_hint"),
        "reservation_confirmed": result.get("reservation_confirmed", False),
        "conversation_state": next_state,
    }
