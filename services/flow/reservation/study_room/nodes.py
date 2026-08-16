from __future__ import annotations

from typing import Dict

from services.flow.reservation.study_room.availability import (
    resolve_study_room_availability,
)
from services.flow.reservation.study_room.generation import (
    generate_study_room_ai_message,
)
from services.flow.reservation.study_room.llm_structured import (
    analyze_study_room_reservation_user_message,
)
from services.flow.reservation.study_room.policy import (
    get_missing_study_room_fields,
)
from services.flow.reservation.study_room.state import StudyRoomReservationState


def extract_study_room_info_node(state: StudyRoomReservationState) -> Dict:
    """
    사용자 발화를 LLM structured output으로 분석하여 스터디룸 예약 정보를 추출한다.
    """
    user_message = state.get("user_message", "") or ""
    conversation_state = state.get("conversation_state") or "greeting"

    analyzed = analyze_study_room_reservation_user_message(
        conversation_state=conversation_state,
        user_message=user_message,
    )

    return {
        "intent": analyzed.get("intent") or state.get("intent") or "reservation",
        "service_name": state.get("service_name") or "마음스터디룸",
        "date": analyzed.get("date") or state.get("date"),
        "start_time": analyzed.get("start_time") or state.get("start_time"),
        "duration": analyzed.get("duration") or state.get("duration"),
        "party_size": analyzed.get("party_size") or state.get("party_size"),
        "user_name": analyzed.get("user_name") or state.get("user_name"),
        "user_action": analyzed.get("user_action") or "unknown",
        "selected_time": analyzed.get("selected_time") or state.get("selected_time"),
        "availability_status": state.get("availability_status"),
        "availability_reason": state.get("availability_reason"),
        "available_time": state.get("available_time"),
        "alternative_times": state.get("alternative_times") or [],
        "availability_message_hint": state.get("availability_message_hint"),
        "reservation_confirmed": state.get("reservation_confirmed", False),
        "last_ai_message": state.get("last_ai_message"),
        "history": state.get("history") or [],
        "recommended_replies": state.get("recommended_replies") or [],
        "should_end_call": state.get("should_end_call", False),
    }


def decide_study_room_state_node(state: StudyRoomReservationState) -> Dict:
    """
    스터디룸 예약 상태를 결정한다.
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
            return _reset_lookup_state(
                {
                    "user_action": user_action,
                    "date": None,
                    "conversation_state": "collecting_reservation_info",
                }
            )

        if user_action == "change_start_time":
            return _reset_lookup_state(
                {
                    "user_action": user_action,
                    "start_time": None,
                    "conversation_state": "collecting_reservation_info",
                }
            )

        if user_action == "change_duration":
            return _reset_lookup_state(
                {
                    "user_action": user_action,
                    "duration": None,
                    "conversation_state": "collecting_reservation_info",
                }
            )

        if user_action == "change_party_size":
            return _reset_lookup_state(
                {
                    "user_action": user_action,
                    "party_size": None,
                    "conversation_state": "collecting_reservation_info",
                }
            )

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
            final_time = (
                state.get("available_time")
                or state.get("selected_time")
                or state.get("start_time")
            )

            return {
                "user_action": user_action,
                "selected_time": final_time,
                "reservation_confirmed": True,
                "conversation_state": "reservation_confirmed",
            }

        if user_action == "ask_other_time":
            return _reset_lookup_state(
                {
                    "user_action": user_action,
                    "start_time": None,
                    "conversation_state": "collecting_reservation_info",
                }
            )

        return {
            "user_action": user_action,
            "conversation_state": "reservation_available",
        }

    if current_state == "reservation_unavailable":
        if user_action == "select_alternative_time":
            selected_time = state.get("selected_time")
            alternative_times = state.get("alternative_times") or []

            if selected_time in alternative_times:
                return {
                    "user_action": user_action,
                    "start_time": selected_time,
                    "selected_time": selected_time,
                    "available_time": selected_time,
                    "availability_status": "available",
                    "availability_reason": None,
                    "availability_message_hint": (
                        f"{state.get('date')} {selected_time}부터 "
                        f"{state.get('duration')} 예약이 가능합니다."
                    ),
                    "reservation_confirmed": False,
                    "conversation_state": "reservation_available",
                }

            return {
                "user_action": user_action,
                "selected_time": None,
                "reservation_confirmed": False,
                "conversation_state": "reservation_unavailable",
            }

        if user_action == "change_date":
            return _reset_lookup_state(
                {
                    "user_action": user_action,
                    "date": None,
                    "start_time": None,
                    "conversation_state": "collecting_reservation_info",
                }
            )

        if user_action == "ask_other_time":
            return _reset_lookup_state(
                {
                    "user_action": user_action,
                    "start_time": None,
                    "conversation_state": "collecting_reservation_info",
                }
            )

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

    missing_fields = get_missing_study_room_fields(state)

    if missing_fields:
        return {
            "user_action": user_action,
            "conversation_state": "collecting_reservation_info",
        }

    return {
        "user_action": user_action,
        "conversation_state": "confirming_info",
    }


def check_study_room_availability_node(state: StudyRoomReservationState) -> Dict:
    """
    스터디룸 예약 가능 여부를 확인한다.
    """
    result = resolve_study_room_availability(state)
    if result["availability_status"] == "available":
        next_state = "reservation_available"
    elif result["availability_status"] == "unavailable":
        next_state = "reservation_unavailable"
    else:
        raise ValueError(
            f"unsupported availability status: {result['availability_status']}"
        )

    return {
        "availability_status": result["availability_status"],
        "availability_reason": result["availability_reason"],
        "available_time": result["available_time"],
        "alternative_times": result["alternative_times"],
        "availability_message_hint": result["availability_message_hint"],
        "reservation_confirmed": result["reservation_confirmed"],
        "conversation_state": next_state,
    }


def generate_study_room_response_node(state: StudyRoomReservationState) -> Dict:
    """
    스터디룸 예약 응답 생성 노드이다.

    검증된 상태를 스터디룸 예약 응답 정책으로 표현한다.
    """
    ai_message = generate_study_room_ai_message(state)

    return {
        "ai_message": ai_message,
        "last_ai_message": ai_message,
    }


def attach_study_room_recommended_replies_node(state: StudyRoomReservationState) -> Dict:
    """
    현재 상태에 맞는 추천 답변을 붙인다.
    """
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"

    if conversation_state == "collecting_reservation_info":
        replies = [
            "내일 오후 2시부터 2시간, 4명 예약하고 싶습니다.",
            "예약자는 김개굴입니다.",
        ]
    elif conversation_state == "confirming_info":
        replies = [
            "네, 맞습니다.",
            "시작 시간을 변경하고 싶습니다.",
            "이용 인원을 수정하고 싶습니다.",
        ]
    elif conversation_state == "reservation_available":
        replies = [
            "네, 그 시간으로 예약해주세요.",
            "다른 시간도 가능할까요?",
        ]
    elif conversation_state == "reservation_unavailable":
        replies = [
            "가능한 다른 시간 알려주세요.",
            "다른 날짜로 예약할게요.",
        ]
    elif conversation_state == "reservation_confirmed":
        replies = [
            "네, 감사합니다.",
        ]
    elif conversation_state == "closing":
        replies = [
            "네, 감사합니다.",
        ]
    else:
        replies = []

    return {
        "recommended_replies": replies,
    }


def _reset_lookup_state(extra: Dict) -> Dict:
    """
    예약 조회와 확정에 관련된 값을 초기화한다.
    """
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
