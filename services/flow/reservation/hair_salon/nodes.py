from __future__ import annotations

from llm.structured_output import apply_action_field_delta
from services.flow.reservation.hair_salon.availability import resolve_hair_salon_availability
from services.flow.reservation.hair_salon.generation import generate_hair_salon_ai_message
from services.flow.reservation.hair_salon.llm_structured import (
    HAIR_SALON_CHANGE_TARGETS,
    analyze_hair_salon_reservation_user_message,
)
from services.flow.reservation.hair_salon.policy import get_missing_hair_salon_fields
from services.flow.reservation.hair_salon.replies import get_hair_salon_recommended_replies
from services.flow.reservation.hair_salon.state import HairSalonReservationState


def extract_hair_salon_info_node(state: HairSalonReservationState) -> dict:
    """
    사용자 발화를 LLM structured output으로 분석한다.

    한 번에 모든 정보를 말하지 않는 사용자를 고려해서,
    새로 분석된 값만 갱신하고 기존 값은 유지한다.
    """
    user_message = state.get("user_message", "") or ""
    conversation_state = state.get("conversation_state") or "greeting"

    analyzed = analyze_hair_salon_reservation_user_message(
        conversation_state,
        user_message,
        alternative_times=state.get("alternative_times") or [],
    )
    current_fields = {
        "date": state.get("date"),
        "time": state.get("time"),
        "service_type": state.get("service_type"),
        "designer": state.get("designer"),
        "user_name": state.get("user_name"),
        "selected_time": state.get("selected_time"),
    }
    next_fields = apply_action_field_delta(
        current_fields,
        {key: analyzed.get(key) for key in current_fields},
        user_action=analyzed["user_action"],
        change_targets=HAIR_SALON_CHANGE_TARGETS,
        reset_actions={"change_info"},
    )

    return {
        "intent": analyzed.get("intent") or state.get("intent") or "reservation",
        "service_name": state.get("service_name") or "마음헤어",
        **next_fields,
        "user_action": analyzed.get("user_action") or "unknown",
        "last_ai_message": state.get("last_ai_message"),
        "history": state.get("history") or [],
        "recommended_replies": state.get("recommended_replies") or [],
        "should_end_call": state.get("should_end_call", False),
    }


def decide_hair_salon_state_node(state: HairSalonReservationState) -> dict:
    """
    미용실 예약 상태를 결정한다.

    - 정보가 부족하면 collecting_reservation_info
    - 정보가 모두 모이면 confirming_info
    - 예약 정보 확인 후 가능 여부를 조회한다
    - 가능/불가 안내 후 사용자 응답에 따라 확정 또는 재수집으로 이동한다
    """
    current_state = state.get("conversation_state") or "greeting"

    user_action = state.get("user_action") or "unknown"

    if current_state == "confirming_info":
        if user_action == "confirm":
            return {
                "user_action": user_action,
                "conversation_state": "checking_availability",
            }

        if user_action == "change_date":
            return _reset_hair_salon_lookup(
                {
                    "user_action": user_action,
                    "date": state.get("date"),
                    "conversation_state": _hair_salon_collection_state(state),
                }
            )

        if user_action == "change_time":
            return _reset_hair_salon_lookup(
                {
                    "user_action": user_action,
                    "time": state.get("time"),
                    "conversation_state": _hair_salon_collection_state(state),
                }
            )

        if user_action == "change_service_type":
            return _reset_hair_salon_lookup(
                {
                    "user_action": user_action,
                    "service_type": state.get("service_type"),
                    "conversation_state": _hair_salon_collection_state(state),
                }
            )

        if user_action == "change_designer":
            return _reset_hair_salon_lookup(
                {
                    "user_action": user_action,
                    "designer": state.get("designer"),
                    "conversation_state": _hair_salon_collection_state(state),
                }
            )

        if user_action == "change_user_name":
            return {
                "user_action": user_action,
                "user_name": state.get("user_name"),
                "reservation_confirmed": False,
                "conversation_state": _hair_salon_collection_state(state),
            }

        if user_action == "change_info":
            return {
                "user_action": user_action,
                "date": None,
                "time": None,
                "service_type": None,
                "designer": None,
                "user_name": None,
                "selected_time": None,
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
            "conversation_state": "confirming_info",
        }

    if current_state == "reservation_available":
        if user_action == "confirm_reservation":
            final_time = (
                state.get("available_time") or state.get("selected_time") or state.get("time")
            )

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
                "selected_time": None,
                "availability_status": None,
                "availability_reason": None,
                "available_time": None,
                "alternative_times": [],
                "availability_message_hint": None,
                "reservation_confirmed": False,
                "conversation_state": "collecting_reservation_info",
            }

        if user_action == "change_date":
            return _reset_hair_salon_lookup(
                {
                    "user_action": user_action,
                    "date": state.get("date"),
                    "conversation_state": _hair_salon_collection_state(state),
                }
            )

        return {
            "user_action": user_action,
            "conversation_state": "reservation_available",
        }

    if current_state == "reservation_unavailable":
        selected_time = state.get("selected_time")
        alternative_times = state.get("alternative_times") or []

        if user_action == "select_alternative_time" and selected_time in alternative_times:
            return {
                "user_action": user_action,
                "time": selected_time,
                "selected_time": selected_time,
                "available_time": selected_time,
                "availability_status": "available",
                "availability_reason": None,
                "availability_message_hint": f"{state.get('date')} {selected_time}에 {state.get('designer')} 선생님 {state.get('service_type')} 예약이 가능합니다.",
                "reservation_confirmed": False,
                "conversation_state": "reservation_available",
            }

        if user_action == "select_alternative_time":
            raise RuntimeError("validated alternative selection is missing from server options")

        if user_action == "change_date":
            return {
                "user_action": user_action,
                "date": state.get("date"),
                "time": None,
                "selected_time": None,
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
            "conversation_state": "collecting_reservation_info",
        }

    return {
        "user_action": user_action,
        "conversation_state": "confirming_info",
    }


def generate_hair_salon_response_node(state: HairSalonReservationState) -> dict:
    """
    미용실 예약 응답 생성 노드이다.

    검증된 상태를 미용실 예약 응답 정책으로 표현한다.
    """
    ai_message = generate_hair_salon_ai_message(state)

    return {
        "ai_message": ai_message,
        "last_ai_message": ai_message,
    }


def attach_hair_salon_recommended_replies_node(state: HairSalonReservationState) -> dict:
    """
    현재 상태에 맞는 추천 답변을 붙인다.
    """
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"

    return {
        "recommended_replies": get_hair_salon_recommended_replies(conversation_state),
    }


def check_hair_salon_availability_node(state: HairSalonReservationState) -> dict:
    """
    미용실 예약 가능 여부를 확인하는 노드이다.
    """
    result = resolve_hair_salon_availability(state)
    if result["availability_status"] == "available":
        next_state = "reservation_available"
    elif result["availability_status"] == "unavailable":
        next_state = "reservation_unavailable"
    else:
        raise ValueError(f"unsupported availability status: {result['availability_status']}")

    return {
        "availability_status": result["availability_status"],
        "availability_reason": result["availability_reason"],
        "available_time": result["available_time"],
        "alternative_times": result["alternative_times"],
        "availability_message_hint": result["availability_message_hint"],
        "reservation_confirmed": result["reservation_confirmed"],
        "selected_time": None,
        "conversation_state": next_state,
    }


def _hair_salon_collection_state(state: HairSalonReservationState) -> str:
    return (
        "collecting_reservation_info" if get_missing_hair_salon_fields(state) else "confirming_info"
    )


def _reset_hair_salon_lookup(extra: dict) -> dict:
    return {
        **extra,
        "selected_time": None,
        "availability_status": None,
        "availability_reason": None,
        "available_time": None,
        "alternative_times": [],
        "availability_message_hint": None,
        "reservation_confirmed": False,
    }
