from __future__ import annotations

from typing import Dict


def build_professor_appointment_template_message(
    conversation_state: str,
    state: Dict,
) -> str:
    """
    LLM 응답이 부적절할 때 사용할 교수님 면담 예약 안전 응답이다.
    """
    professor_name = state.get("professor_name") or "교수님"
    purpose = state.get("appointment_purpose") or "면담 목적"
    date = state.get("date") or "희망 날짜"
    time = state.get("time") or "희망 시간"
    user_name = state.get("user_name") or "학생"

    if conversation_state == "collecting_appointment_info":
        missing_fields = state.get("missing_fields") or []

        if "appointment_purpose" in missing_fields:
            return f"네, {professor_name}입니다. 면담을 희망하시는 구체적인 목적을 말씀해주시겠습니까?"

        if "date" in missing_fields:
            return f"{purpose} 관련 면담으로 확인했습니다. 희망하시는 날짜를 말씀해주시겠습니까?"

        if "time" in missing_fields:
            return f"{date} 면담으로 확인했습니다. 희망하시는 시간을 말씀해주시겠습니까?"

        if "user_name" in missing_fields:
            return f"{date} {time}, {purpose} 관련 면담으로 확인했습니다. 성함을 말씀해주시겠습니까?"

        return _build_confirming_message(state)

    if conversation_state == "confirming_info":
        return _build_confirming_message(state)

    if conversation_state == "closing":
        return "네, 확인했습니다. 해당 일정으로 참고하겠습니다."

    if conversation_state == "END":
        return "네, 알겠습니다."

    return f"네, {professor_name}입니다. 면담 예약 관련해서 말씀해주시겠습니까?"


def _build_confirming_message(state: Dict) -> str:
    date = state.get("date") or "희망 날짜"
    time = state.get("time") or "희망 시간"
    purpose = state.get("appointment_purpose") or "면담 목적"
    user_name = state.get("user_name") or "학생"

    return (
        f"{user_name} 학생, {date} {time}에 {purpose} 관련 면담을 희망하시는 것으로 "
        "확인했습니다. 맞습니까?"
    )
