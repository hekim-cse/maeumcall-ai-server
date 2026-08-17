from __future__ import annotations

from services.flow.reservation.study_room.policy import (
    get_missing_study_room_fields,
)

STUDY_ROOM_FIELD_LABELS = {
    "date": "이용 날짜",
    "start_time": "시작 시간",
    "duration": "이용 시간",
    "party_size": "인원",
    "user_name": "예약자 성함",
}


def choose_message(candidates: list[str], state: dict) -> str:
    last_ai_message = state.get("last_ai_message")

    for message in candidates:
        if message != last_ai_message:
            return message

    if not candidates:
        raise ValueError("study room response policy requires at least one candidate")
    return candidates[0]


def build_study_room_response(conversation_state: str, state: dict = None) -> str:
    """
    검증된 스터디룸 예약 상태에 맞는 제품 응답을 생성한다.
    """
    state = state or {}

    date = state.get("date") or "원하시는 날짜"
    start_time = state.get("start_time") or "원하시는 시간"
    duration = state.get("duration") or "이용 시간"
    party_size = state.get("party_size") or "인원"

    if conversation_state == "collecting_reservation_info":
        missing = get_missing_study_room_fields(state)
        if missing == ["user_name"]:
            return "예약자 성함을 말씀해주시겠어요?"
        if not missing:
            raise ValueError("collecting_reservation_info requires at least one missing field")
        fields = ", ".join(STUDY_ROOM_FIELD_LABELS[field] for field in missing)
        return f"스터디룸 예약 도와드리겠습니다. 필요한 정보는 {fields}입니다."

    if conversation_state == "confirming_info":
        return (
            f"{date} {start_time}부터 {duration}, {party_size} 예약으로 확인했습니다. 맞으실까요?"
        )

    if conversation_state == "checking_availability":
        return "잠시만요. 예약 가능한지 확인해보겠습니다."

    if conversation_state == "reservation_available":
        available_time = state.get("available_time") or state.get("selected_time") or start_time
        return f"{date} {available_time}부터 {duration}, {party_size} 예약 가능합니다. 이 시간 괜찮으세요?"

    if conversation_state == "reservation_unavailable":
        alternatives = state.get("alternative_times") or []
        if alternatives:
            alternatives_text = " 또는 ".join(alternatives)
            return f"죄송하지만 요청하신 시간은 예약이 어렵습니다. 대신 {alternatives_text}부터는 가능합니다."

        return "죄송하지만 해당 시간은 예약이 어렵습니다. 다른 시간대로 확인해드릴까요?"

    if conversation_state == "reservation_confirmed":
        final_time = state.get("selected_time") or state.get("available_time") or start_time
        return f"예약 완료됐습니다. {date} {final_time}부터 {duration} 이용해주시면 됩니다."

    if conversation_state == "closing":
        return "감사합니다. 좋은 하루 보내세요."

    if conversation_state == "END":
        return "감사합니다. 좋은 하루 보내세요."

    raise ValueError(f"unsupported study room conversation state: {conversation_state}")
