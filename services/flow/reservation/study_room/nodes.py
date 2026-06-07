from __future__ import annotations

from typing import Dict

from services.flow.reservation.study_room.state import StudyRoomReservationState
from services.flow.reservation.study_room.extractor import extract_study_room_reservation_info
from services.flow.reservation.study_room.policy import get_missing_study_room_fields


def extract_study_room_info_node(state: StudyRoomReservationState) -> Dict:
    """
    사용자 발화에서 스터디룸 예약 정보를 추출한다.

    사용자가 정보를 한 번에 모두 말하지 않을 수 있으므로
    새로 추출된 값만 갱신하고 기존 값은 유지한다.
    """
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
        "last_ai_message": state.get("last_ai_message"),
        "history": state.get("history") or [],
        "recommended_replies": state.get("recommended_replies") or [],
        "should_end_call": state.get("should_end_call", False),
    }


def decide_study_room_state_node(state: StudyRoomReservationState) -> Dict:
    """
    스터디룸 예약 상태를 결정한다.

    정보가 부족하면 collecting_reservation_info,
    정보가 모두 모이면 confirming_info로 이동한다.
    """
    missing_fields = get_missing_study_room_fields(state)

    if missing_fields:
        return {
            "missing_fields": missing_fields,
            "conversation_state": "collecting_reservation_info",
        }

    return {
        "missing_fields": [],
        "conversation_state": "confirming_info",
    }


def generate_study_room_response_node(state: StudyRoomReservationState) -> Dict:
    """
    스터디룸 예약 응답을 생성한다.
    """
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"

    if conversation_state == "collecting_reservation_info":
        ai_message = _build_collecting_info_message(state)
    elif conversation_state == "confirming_info":
        ai_message = _build_confirming_info_message(state)
    else:
        ai_message = "스터디룸 예약 도와드리겠습니다."

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
    else:
        replies = [
            "내일 오후 두 시부터 두 시간 이용하고 싶습니다.",
            "4명이고 김개굴 이름으로 예약해주세요.",
            "오늘 오후 3시부터 2시간 가능할까요?",
        ]

    return {
        "recommended_replies": replies,
    }


def _build_collecting_info_message(state: StudyRoomReservationState) -> str:
    """
    부족한 스터디룸 예약 정보를 자연스럽게 묶어서 묻는다.
    """
    missing_fields = get_missing_study_room_fields(state)

    service_name = state.get("service_name") or "마음스터디룸"
    date = state.get("date")
    start_time = state.get("start_time")
    duration = state.get("duration")
    party_size = state.get("party_size")
    user_name = state.get("user_name")

    known_parts = []

    if date:
        known_parts.append(date)

    if start_time:
        known_parts.append(f"{start_time}부터")

    if duration:
        known_parts.append(duration)

    if party_size:
        known_parts.append(party_size)

    if user_name:
        known_parts.append(f"{user_name}님")

    known_text = " ".join(known_parts)

    if len(missing_fields) == 5:
        return (
            f"네, {service_name}입니다. 스터디룸 예약 도와드리겠습니다. "
            "이용하실 날짜, 시작 시간, 이용 시간, 인원, 예약자 성함을 편하게 말씀해주시겠어요?"
        )

    if "party_size" in missing_fields and "user_name" in missing_fields:
        return f"{known_text} 이용으로 확인했습니다. 이용 인원과 예약자 성함을 말씀해주시겠어요?"

    if "duration" in missing_fields and "party_size" in missing_fields:
        return f"{known_text} 이용으로 확인했습니다. 이용 시간과 인원은 어떻게 되실까요?"

    if "start_time" in missing_fields and "duration" in missing_fields:
        return f"{known_text} 이용으로 확인했습니다. 시작 시간과 이용 시간을 말씀해주시겠어요?"

    if "date" in missing_fields:
        return f"{known_text} 스터디룸 예약으로 확인했습니다. 이용 날짜는 언제가 괜찮으세요?"

    if "start_time" in missing_fields:
        return f"{known_text} 이용으로 확인했습니다. 몇 시부터 이용하시겠어요?"

    if "duration" in missing_fields:
        return f"{known_text} 이용으로 확인했습니다. 몇 시간 이용하실 예정이세요?"

    if "party_size" in missing_fields:
        return f"{known_text} 이용으로 확인했습니다. 몇 분이서 이용하시나요?"

    if "user_name" in missing_fields:
        return f"{known_text} 이용 예약으로 확인했습니다. 예약자 성함은 어떻게 남겨드릴까요?"

    return _build_confirming_info_message(state)


def _build_confirming_info_message(state: StudyRoomReservationState) -> str:
    """
    수집된 스터디룸 예약 정보를 확인한다.
    """
    date = state.get("date") or "예약 날짜"
    start_time = state.get("start_time") or "시작 시간"
    duration = state.get("duration") or "이용 시간"
    party_size = state.get("party_size") or "인원"
    user_name = state.get("user_name") or "예약자"

    return (
        f"{date} {start_time}부터 {duration}, {party_size}, "
        f"{user_name}님 예약으로 확인했습니다. 맞으실까요?"
    )
