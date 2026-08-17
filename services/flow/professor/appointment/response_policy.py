from __future__ import annotations


def build_professor_appointment_response(conversation_state: str, state: dict) -> str:
    professor_name = state.get("professor_name") or "교수님"
    purpose = state.get("appointment_purpose") or "면담 목적"
    date = state.get("date") or "희망 날짜"
    time = state.get("time") or "희망 시간"
    user_name = state.get("user_name") or "학생"

    if conversation_state == "collecting_appointment_info":
        missing = state.get("missing_fields") or []
        if "appointment_purpose" in missing:
            return (
                f"네, {professor_name}입니다. 면담을 희망하시는 구체적인 목적을 말씀해주시겠습니까?"
            )
        if "date" in missing:
            return f"{purpose} 관련 면담으로 확인했습니다. 희망하시는 날짜를 말씀해주시겠습니까?"
        if "time" in missing:
            return f"{date} 면담으로 확인했습니다. 희망하시는 시간을 말씀해주시겠습니까?"
        if "user_name" in missing:
            return (
                f"{date} {time}, {purpose} 관련 면담으로 확인했습니다. 성함을 말씀해주시겠습니까?"
            )
        return _confirmation(state)
    if conversation_state == "confirming_info":
        return _confirmation(state)
    if conversation_state == "appointment_confirmed":
        return f"알겠습니다. {user_name} 학생의 {purpose} 관련 면담 요청은 {date} {time}로 확인해두겠습니다."
    if conversation_state == "closing":
        return "네, 확인했습니다. 추가로 필요한 사항이 있으면 다시 말씀해주시기 바랍니다."
    if conversation_state == "END":
        return "네, 알겠습니다."
    raise ValueError(f"unsupported professor appointment state: {conversation_state}")


def _confirmation(state: dict) -> str:
    return (
        f"{state.get('user_name') or '학생'} 학생, {state.get('date') or '희망 날짜'} "
        f"{state.get('time') or '희망 시간'}에 {state.get('appointment_purpose') or '면담 목적'} 관련 면담을 "
        "희망하시는 것으로 확인했습니다. 맞습니까?"
    )
