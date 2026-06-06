from __future__ import annotations

from typing import Dict

from services.flow.reservation.restaurant.state import RestaurantReservationState
from services.flow.reservation.restaurant.action_parser import parse_restaurant_reservation_action
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
    식당 예약 상태를 결정한다.

    중요:
    - 이미 confirming_info, reservation_available 같은 진행 상태에 들어온 경우에는
      사용자의 확인/변경 의도를 먼저 처리한다.
    - 그 다음에 부족한 예약 정보를 판단한다.
    - 정보가 모두 모이면 confirming_info로 이동한다.
    """
    user_message = state.get("user_message", "") or ""
    current_state = state.get("conversation_state") or "greeting"

    action_result = parse_restaurant_reservation_action(
        current_state,
        user_message,
    )
    user_action = action_result.get("user_action")

    # 1) 예약 정보 확인 상태에서 사용자가 맞다고 한 경우
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

        if user_action == "change_party_size":
            return {
                "user_action": user_action,
                "party_size": None,
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

    # 2) 예약 가능 안내 후 사용자가 확정한 경우
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

        return {
            "user_action": user_action,
            "conversation_state": "reservation_available",
        }

    # 3) 예약 불가 안내 후 사용자가 다른 날짜/시간을 요청한 경우
    if current_state == "reservation_unavailable":
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

    # 4) 예약 완료 후 마무리
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

    # 5) 일반 정보 수집 흐름
    date = state.get("date")
    time = state.get("time")
    party_size = state.get("party_size")
    user_name = state.get("user_name")

    missing_fields = []

    if not date:
        missing_fields.append("date")

    if not time:
        missing_fields.append("time")

    if not party_size:
        missing_fields.append("party_size")

    if not user_name:
        missing_fields.append("user_name")

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


def check_restaurant_availability_node(state: RestaurantReservationState) -> Dict:
    """
    식당 예약 가능 여부를 확인하는 노드이다.

    실제 예약 시스템 연동 전까지는 resolve_restaurant_availability의
    규칙 기반 시뮬레이션 결과를 사용한다.
    """
    result = resolve_restaurant_availability(state)

    availability_status = result.get("availability_status")

    if availability_status == "available":
        next_state = "reservation_available"
    elif availability_status == "unavailable":
        next_state = "reservation_unavailable"
    else:
        next_state = "reservation_unavailable"

    return {
        **result,
        "conversation_state": next_state,
        "simulation_result": result,
    }
