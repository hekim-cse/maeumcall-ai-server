from __future__ import annotations

from typing import Dict

from services.flow.reservation.hair_salon.state import HairSalonReservationState
from services.flow.reservation.hair_salon.extractor import extract_hair_salon_reservation_info
from services.flow.reservation.hair_salon.generation import generate_hair_salon_ai_message
from services.flow.reservation.hair_salon.policy import get_missing_hair_salon_fields
from services.flow.reservation.hair_salon.replies import get_hair_salon_recommended_replies


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

    이번 단계에서는 정보 수집 상태까지만 처리한다.
    모든 예약 정보가 모이면 confirming_info로 이동한다.
    """
    missing_fields = get_missing_hair_salon_fields(state)

    if missing_fields:
        return {
            "missing_fields": missing_fields,
            "conversation_state": "collecting_reservation_info",
        }

    return {
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
