from __future__ import annotations

from typing import Dict

from services.flow.reservation.study_room.state import StudyRoomReservationState
from services.flow.reservation.study_room.extractor import extract_study_room_reservation_info
from services.flow.reservation.study_room.policy import get_missing_study_room_fields
from services.flow.reservation.study_room.action_parser import parse_study_room_reservation_action
from services.flow.reservation.study_room.availability import resolve_study_room_availability
from services.flow.reservation.study_room.generation import generate_study_room_ai_message
from services.flow.reservation.study_room.templates import build_study_room_template_message


def extract_study_room_info_node(state: StudyRoomReservationState) -> Dict:
    user_message = state.get("user_message", "") or ""
    extracted = extract_study_room_reservation_info(user_message)

    return {
        "intent": extracted.get("intent") or state.get("intent") or "reservation",
        "service_name": state.get("service_name") or "마음스터디룸",
        "date": extracted.get("date") or state.get("date"),
        "start_time": extracted.get("start_time") or state.get("start_time"),
        "duration": extracted.get("duration") or state.get("duration"),
        "party_size": extracted.get("party_size") or state.get("party_size"),
        "user_name": extracted.get("user_name") or state.get("user_name"),
        "selected_time": state.get("selected_time"),
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
    user_message = state.get("user_message", "") or ""
    current_state = state.get("conversation_state") or "greeting"

    action_result = parse_study_room_reservation_action(
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
            final_time = state.get("available_time") or state.get("selected_time") or state.get("start_time")

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
            selected_time = action_result.get("selected_time")
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
                        f"{state.get('date')} {selected_time}부터 {state.get('duration')} 예약이 가능합니다."
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
            "missing_fields": missing_fields,
            "conversation_state": "collecting_reservation_info",
        }

    return {
        "user_action": user_action,
        "missing_fields": [],
        "conversation_state": "confirming_info",
    }


def check_study_room_availability_node(state: StudyRoomReservationState) -> Dict:
    """
    스터디룸 예약 가능 여부를 확인한다.
    """
    result = resolve_study_room_availability(state)
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


def generate_study_room_response_node(state: StudyRoomReservationState) -> Dict:
    """
    스터디룸 예약 응답 생성 노드이다.

    기본은 LLM 응답을 우선 사용한다.
    다만 테스트와 실제 통화 흐름에서 반드시 보장되어야 하는 핵심 표현은
    마지막 단계에서 안전하게 보정한다.
    """
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"
    missing_fields = state.get("missing_fields") or get_missing_study_room_fields(state)

    # 예약자 이름만 부족한 경우에는 이미 수집된 날짜/시간/인원을 다시 묻지 않는다.
    if conversation_state == "collecting_reservation_info" and missing_fields == ["user_name"]:
        date = state.get("date") or "예약 날짜"
        start_time = state.get("start_time") or "시작 시간"
        duration = state.get("duration") or "이용 시간"
        party_size = state.get("party_size") or "인원"

        ai_message = (
            f"{date} {start_time}부터 {duration}, {party_size} 이용 예약으로 확인했습니다. "
            "예약자 성함은 어떻게 남겨드릴까요?"
        )
    else:
        ai_message = generate_study_room_ai_message(state)

    # 예약 불가 상태에서는 사용자에게 불가 의미가 명확히 전달되어야 한다.
    if conversation_state == "reservation_unavailable":
        unavailable_keywords = ["어렵", "어려운", "마감", "불가능"]
        if not any(keyword in ai_message for keyword in unavailable_keywords):
            alternatives = state.get("alternative_times") or []
            alternatives_text = " 또는 ".join(alternatives)

            if alternatives_text:
                ai_message = (
                    f"죄송하지만 요청하신 시간은 예약이 어렵습니다. "
                    f"대신 {alternatives_text}부터는 가능합니다."
                )
            else:
                ai_message = "죄송하지만 해당 시간은 예약이 어렵습니다. 다른 시간대로 확인해드릴까요?"

    return {
        "ai_message": ai_message,
        "last_ai_message": ai_message,
    }


def attach_study_room_recommended_replies_node(state: StudyRoomReservationState) -> Dict:
    """
    현재 상태에 맞는 추천 답변을 붙인다.
    """
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"

    if conversation_state == "confirming_info":
        replies = [
            "네, 맞습니다.",
            "시간을 바꾸고 싶습니다.",
            "인원을 변경하고 싶습니다.",
        ]
    elif conversation_state == "reservation_available":
        replies = [
            "네, 예약해주세요.",
            "다른 시간 가능할까요?",
            "날짜를 바꾸고 싶습니다.",
        ]
    elif conversation_state == "reservation_unavailable":
        replies = [
            "오후 1시로 할게요.",
            "오후 3시로 할게요.",
            "다른 날짜로 확인해주세요.",
        ]
    elif conversation_state == "reservation_confirmed":
        replies = [
            "네, 감사합니다.",
            "확인했습니다.",
        ]
    elif conversation_state == "closing":
        replies = [
            "네, 감사합니다.",
        ]
    else:
        replies = [
            "내일 오후 두 시부터 두 시간 이용하고 싶습니다.",
            "4명이고 김개굴 이름으로 예약해주세요.",
            "오늘 오후 3시부터 2시간 가능할까요?",
        ]

    return {
        "recommended_replies": replies,
    }


def _reset_lookup_state(extra: Dict) -> Dict:
    """
    날짜/시간/이용 시간 등 예약 조건이 바뀌면 기존 예약 조회 결과를 초기화한다.
    """
    return {
        **extra,
        "availability_status": None,
        "availability_reason": None,
        "available_time": None,
        "alternative_times": [],
        "availability_message_hint": None,
        "reservation_confirmed": False,
    }
