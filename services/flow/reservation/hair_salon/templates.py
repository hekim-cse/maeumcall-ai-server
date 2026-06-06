from __future__ import annotations

from typing import List


def choose_message(candidates: List[str], state: dict) -> str:
    last_ai_message = state.get("last_ai_message")

    for message in candidates:
        if message != last_ai_message:
            return message

    return candidates[0] if candidates else ""


def build_hair_salon_template_message(conversation_state: str, state: dict = None) -> str:
    """
    미용실 예약 상태에 맞는 fallback 응답을 생성한다.
    """
    state = state or {}

    date = state.get("date") or "원하시는 날짜"
    time = state.get("time") or "원하시는 시간"
    service_type = state.get("service_type") or "원하시는 시술"
    designer = state.get("designer") or "원하시는 디자이너"
    user_name = state.get("user_name") or "예약자 성함"

    if conversation_state == "collecting_reservation_info":
        return "예약 도와드리겠습니다. 원하시는 날짜, 시간, 시술 종류, 디자이너 선생님을 편하게 말씀해주시겠어요?"

    if conversation_state == "confirming_info":
        return f"{date} {time}에 {designer} 선생님으로 {service_type} 예약을 원하시는 것이 맞으실까요?"

    if conversation_state == "checking_availability":
        return "잠시만요. 예약 가능한지 확인해보겠습니다."

    if conversation_state == "reservation_available":
        available_time = state.get("available_time") or state.get("selected_time") or time
        return f"{date} {available_time}에 {designer} 선생님으로 {service_type} 예약 가능합니다. 이 시간 괜찮으세요?"

    if conversation_state == "reservation_unavailable":
        alternatives = state.get("alternative_times") or []
        if alternatives:
            alternatives_text = " 또는 ".join(alternatives)
            return f"죄송하지만 요청하신 시간은 예약이 어렵습니다. 대신 {alternatives_text}는 가능합니다. 괜찮으신 시간이 있으세요?"

        return "죄송하지만 요청하신 시간은 예약이 어렵습니다. 다른 시간대로 확인해드릴까요?"

    if conversation_state == "reservation_confirmed":
        final_time = state.get("selected_time") or state.get("available_time") or time
        return f"{user_name}님, {date} {final_time}에 {designer} 선생님 {service_type} 예약 완료됐습니다."

    if conversation_state == "closing":
        return "네, 감사합니다. 방문 때 뵙겠습니다."

    if conversation_state == "END":
        return "감사합니다. 좋은 하루 보내세요."

    return "미용실 예약 도와드리겠습니다. 원하시는 날짜와 시간을 말씀해주세요."
