from __future__ import annotations

from typing import Dict, List

from services.flow.reservation.hair_salon.state import HairSalonReservationState
from services.flow.reservation.hair_salon.llm_client import complete_hair_salon_ai_message
from services.flow.reservation.hair_salon.validator import is_valid_hair_salon_ai_message
from services.flow.reservation.hair_salon.templates import build_hair_salon_template_message


def format_history_for_prompt(history: List[Dict[str, str]], max_turns: int = 6) -> str:
    """
    최근 대화 기록을 LLM prompt에 넣기 좋은 형태로 정리한다.
    """
    recent_history = (history or [])[-max_turns:]

    if not recent_history:
        return "이전 대화 없음"

    lines = []
    for turn in recent_history:
        role = turn.get("role") or "unknown"
        text = turn.get("text") or turn.get("content") or ""
        lines.append(f"{role}: {text}")

    return "\n".join(lines)


def build_hair_salon_ai_message_prompt(state: HairSalonReservationState) -> str:
    """
    미용실 예약 응답 생성을 위한 LLM prompt를 만든다.
    """
    service_name = state.get("service_name") or "마음헤어"
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"

    date = state.get("date") or "미확인"
    time = state.get("time") or "미확인"
    service_type = state.get("service_type") or "미확인"
    designer = state.get("designer") or "미확인"
    user_name = state.get("user_name") or "미확인"

    available_time = state.get("available_time") or state.get("selected_time") or time
    alternatives = state.get("alternative_times") or []
    alternatives_text = ", ".join(alternatives) if alternatives else "없음"

    history_text = format_history_for_prompt(state.get("history") or [])

    state_rules = {
        "collecting_reservation_info": (
            "예약에 필요한 정보 중 부족한 항목을 자연스럽게 요청한다. "
            "날짜, 시간, 시술 종류, 디자이너, 예약자 성함 중 이미 확인된 정보는 다시 묻지 않는다."
        ),
        "confirming_info": (
            "확인된 예약 정보를 짧게 다시 말하고, 맞는지 확인한다. "
            "예약 가능 여부를 아직 말하지 않는다."
        ),
        "checking_availability": (
            "예약 가능 여부를 확인해보겠다고 말한다. "
            "가능/불가능 결과를 아직 말하지 않는다."
        ),
        "reservation_available": (
            "예약 가능한 시간임을 안내하고, 이 시간으로 진행할지 묻는다. "
            "예약 완료라고 말하지 않는다."
        ),
        "reservation_unavailable": (
            "요청한 시간 예약이 어렵다고 안내하고, 대안 시간이 있으면 제안한다."
        ),
        "reservation_confirmed": (
            "예약이 완료되었다고 한 문장으로 안내한다."
        ),
        "closing": (
            "짧고 자연스럽게 마무리 인사를 한다."
        ),
        "END": (
            "통화를 종료하는 짧은 인사를 한다."
        ),
    }

    task = state_rules.get(conversation_state, "현재 상태에 맞는 미용실 예약 직원 응답을 한 문장으로 작성한다.")

    return f"""
너는 {service_name} 예약 전화를 받는 직원이다.

[현재 상태]
conversation_state: {conversation_state}

[사용자 발화]
{state.get("user_message") or ""}

[현재까지 확인된 예약 정보]
- 날짜: {date}
- 시간: {time}
- 시술 종류: {service_type}
- 디자이너: {designer}
- 예약자 이름: {user_name}
- 예약 가능 시간: {available_time}
- 대안 시간: {alternatives_text}

[이전 대화]
{history_text}

[응답 규칙]
- 한국어로 답한다.
- 한 문장 또는 두 문장 이내로 답한다.
- 실제 미용실 직원처럼 자연스럽게 답한다.
- 콜 포비아 사용자가 부담을 덜 느끼도록 부드럽게 말한다.
- 예약 확정 전에는 "예약 완료"라고 말하지 않는다.
- 모르는 정보를 지어내지 않는다.
- 현재 상태에 필요한 말만 한다.

[이번 응답 목표]
{task}
""".strip()


def generate_hair_salon_ai_message(state: HairSalonReservationState) -> str:
    """
    미용실 예약 ai_message를 생성한다.

    LLM 응답을 우선 사용하고,
    상태 검증에 실패하면 template fallback을 사용한다.
    """
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"

    prompt = build_hair_salon_ai_message_prompt(state)

    try:
        ai_message = complete_hair_salon_ai_message(prompt).strip()

        if is_valid_hair_salon_ai_message(conversation_state, ai_message):
            return ai_message

    except Exception:
        pass

    return build_hair_salon_template_message(conversation_state, state)
