from __future__ import annotations

from typing import Dict, List

from services.flow.reservation.restaurant.state import RestaurantReservationState
from services.flow.reservation.restaurant.llm_client import complete_restaurant_ai_message
from services.flow.reservation.restaurant.templates import build_restaurant_template_message
from services.flow.reservation.restaurant.validator import validate_restaurant_reservation_message


def format_history_for_prompt(history: List[Dict[str, str]], max_turns: int = 6) -> str:
    """
    최근 대화 기록을 LLM prompt에 넣기 좋은 문자열로 변환한다.
    """
    if not history:
        return "없음"

    recent_history = history[-max_turns:]

    lines = []
    for item in recent_history:
        role = item.get("role", "")
        content = item.get("content") or item.get("text") or ""

        if not content:
            continue

        if role == "user":
            lines.append(f"사용자: {content}")
        elif role in ["assistant", "ai"]:
            lines.append(f"AI: {content}")

    return "\n".join(lines) if lines else "없음"


def should_use_restaurant_template_first(conversation_state: str) -> bool:
    """
    정형 응답이 더 안전한 상태는 LLM보다 template을 먼저 사용한다.
    """
    return conversation_state in {
        "checking_availability",
        "reservation_confirmed",
        "closing",
        "END",
    }


def build_restaurant_ai_prompt(state: RestaurantReservationState) -> str:
    """
    식당 예약 응답 생성을 위한 LLM prompt를 만든다.
    """
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"
    service_name = state.get("service_name") or "마음식당"

    date = state.get("date") or "없음"
    time = state.get("time") or "없음"
    party_size = state.get("party_size") or "없음"
    user_name = state.get("user_name") or "없음"
    user_message = state.get("user_message") or ""

    missing_fields = state.get("missing_fields") or []
    history_text = format_history_for_prompt(state.get("history") or [])
    last_ai_message = state.get("last_ai_message") or "없음"

    if conversation_state == "collecting_reservation_info":
        task = (
            "예약에 필요한 정보 중 부족한 항목을 자연스럽게 요청한다. "
            "이미 확인된 정보는 다시 묻지 않는다. "
            "부족한 정보가 여러 개면 한 문장 안에서 자연스럽게 묶어서 물어본다."
        )
    elif conversation_state == "confirming_info":
        task = (
            "확인된 예약 정보를 짧게 다시 말하고, 맞는지 확인한다. "
            "예약 가능 여부를 아직 말하지 않는다."
        )
    elif conversation_state == "reservation_available":
        task = (
            "예약 가능한 시간임을 안내하고, 이 시간으로 진행할지 묻는다."
        )
    elif conversation_state == "reservation_unavailable":
        task = (
            "요청한 시간은 어렵다고 안내하고, 가능한 대안 시간이 있으면 자연스럽게 제안한다."
        )
    else:
        task = "현재 상태에 맞는 식당 예약 직원 응답을 한 문장으로 작성한다."

    return f"""
너는 {service_name} 예약 전화를 받는 직원이다.

[현재 상태]
- conversation_state: {conversation_state}
- date: {date}
- time: {time}
- party_size: {party_size}
- user_name: {user_name}
- missing_fields: {missing_fields}

[사용자 최근 발화]
{user_message}

[최근 대화 기록]
{history_text}

[직전 AI 응답]
{last_ai_message}

[해야 할 일]
{task}

[규칙]
- 식당 직원의 응답 한 문장만 출력한다.
- JSON, markdown, 따옴표, assistant, user를 출력하지 않는다.
- 너무 기계적으로 하나씩 캐묻지 않는다.
- 콜 포비아 사용자가 부담을 덜 느끼도록 부드럽게 말한다.
- 이미 확인된 정보는 다시 묻지 않는다.
- 예약 확정 전에는 "예약 완료"라고 말하지 않는다.
""".strip()


def clean_restaurant_ai_message(text: str) -> str:
    """
    LLM 응답에서 불필요한 라벨과 따옴표를 정리한다.
    """
    cleaned = (text or "").strip()

    for prefix in ["assistant:", "Assistant:", "AI:", "ai:", "직원:"]:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()

    return cleaned.strip("\"'“”‘’ ")


def generate_restaurant_ai_message(state: RestaurantReservationState) -> Dict:
    """
    식당 예약 ai_message를 생성한다.

    template-first 상태는 정형 응답을 사용하고,
    그 외 상태는 LLM 응답을 먼저 시도한 뒤 검증 실패 시 template으로 fallback한다.
    """
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"

    if should_use_restaurant_template_first(conversation_state):
        return {
            "ai_message": build_restaurant_template_message(conversation_state, state)
        }

    prompt = build_restaurant_ai_prompt(state)
    raw_message = complete_restaurant_ai_message(prompt)
    ai_message = clean_restaurant_ai_message(raw_message)

    if validate_restaurant_reservation_message(conversation_state, ai_message):
        return {"ai_message": ai_message}

    return {
        "ai_message": build_restaurant_template_message(conversation_state, state)
    }
