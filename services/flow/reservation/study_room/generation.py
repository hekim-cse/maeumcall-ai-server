from __future__ import annotations

from services.flow.reservation.study_room.llm_client import complete_study_room_ai_message
from services.flow.reservation.study_room.templates import build_study_room_template_message
from services.flow.reservation.study_room.validator import is_valid_study_room_response


def build_study_room_generation_prompt(state: dict) -> str:
    """
    스터디룸 예약 응답 생성을 위한 LLM prompt를 만든다.
    """
    service_name = state.get("service_name") or "마음스터디룸"
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"

    date = state.get("date")
    start_time = state.get("start_time")
    duration = state.get("duration")
    party_size = state.get("party_size")
    user_name = state.get("user_name")
    available_time = state.get("available_time")
    alternative_times = state.get("alternative_times") or []
    availability_message_hint = state.get("availability_message_hint")

    if conversation_state == "collecting_reservation_info":
        task = "예약에 필요한 정보 중 부족한 항목을 자연스럽게 요청한다."
    elif conversation_state == "confirming_info":
        task = "확인된 예약 정보를 짧게 다시 말하고, 맞는지 확인한다. 예약 가능 여부는 아직 말하지 않는다."
    elif conversation_state == "checking_availability":
        task = "사용자가 예약 정보가 맞다고 확인했다. 예약 가능 여부를 확인해보겠다고 말하고 잠시 기다려달라고 안내한다."
    elif conversation_state == "reservation_available":
        task = "예약 가능한 시간임을 안내하고, 이 시간으로 진행할지 묻는다."
    elif conversation_state == "reservation_unavailable":
        task = "요청한 시간 예약이 어렵다고 안내하고, 가능한 대안 시간이 있으면 제안한다."
    elif conversation_state == "reservation_confirmed":
        task = "예약이 완료되었다고 한 문장으로 안내한다."
    elif conversation_state in ["closing", "END"]:
        task = "짧게 감사 인사를 하고 통화를 마무리한다."
    else:
        task = "현재 상태에 맞는 스터디룸 예약 직원 응답을 한 문장으로 작성한다."

    alternatives_text = ", ".join(alternative_times) if alternative_times else "없음"

    return f"""
너는 {service_name} 예약 전화를 받는 직원이다.

현재 대화 상태:
- conversation_state: {conversation_state}
- date: {date}
- start_time: {start_time}
- duration: {duration}
- party_size: {party_size}
- user_name: {user_name}
- available_time: {available_time}
- alternative_times: {alternatives_text}
- availability_message_hint: {availability_message_hint}

응답 목표:
{task}

응답 규칙:
- 한국어로 답한다.
- 실제 전화 직원처럼 자연스럽게 말한다.
- 사용자를 압박하지 않는다.
- 한 번에 너무 많은 정보를 요구하지 않는다.
- 1문장 또는 2문장으로 짧게 답한다.
- 예약 확정 전에는 "예약 완료"라고 말하지 않는다.
- reservation_available 상태에서는 반드시 "가능"이라는 표현을 포함한다.
- reservation_unavailable 상태에서는 반드시 "어렵", "마감", "불가능" 중 하나의 의미를 포함한다.
- reservation_confirmed 상태에서만 예약 완료 표현을 사용한다.
"""


def generate_study_room_ai_message(state: dict) -> str:
    """
    스터디룸 예약 ai_message를 생성한다.

    LLM 응답을 우선 사용하고,
    상태 의미와 맞지 않으면 template fallback을 사용한다.
    """
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"
    fallback = build_study_room_template_message(conversation_state, state)

    try:
        prompt = build_study_room_generation_prompt(state)
        ai_message = complete_study_room_ai_message(prompt)

        if is_valid_study_room_response(conversation_state, ai_message):
            return ai_message

        return fallback

    except Exception:
        return fallback
