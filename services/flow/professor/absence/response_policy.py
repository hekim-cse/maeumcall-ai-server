from __future__ import annotations

from typing import Dict


def build_professor_absence_response(conversation_state: str, state: Dict) -> str:
    professor_name = state.get("professor_name") or "교수님"
    absence_date = state.get("absence_date") or "결석 날짜"
    user_name = state.get("user_name") or "학생"

    if conversation_state == "collecting_absence_info":
        missing = state.get("missing_fields") or []
        if "absence_date" in missing:
            return f"네, {professor_name}입니다. 결석하게 되는 날짜를 말씀해주시겠습니까?"
        if "absence_reason" in missing:
            return f"{absence_date} 결석으로 확인했습니다. 결석 사유를 말씀해주시겠습니까?"
        if "user_name" in missing:
            return f"{absence_date} 결석 사유는 확인했습니다. 성함을 말씀해주시겠습니까?"
        return _confirmation(state)
    if conversation_state == "confirming_absence_info":
        return _confirmation(state)
    if conversation_state == "absence_noted":
        return f"알겠습니다. {user_name} 학생의 {absence_date} 결석 사유는 참고하도록 하겠습니다."
    if conversation_state == "closing":
        return "네, 확인했습니다. 추후 필요한 사항이 있으면 다시 말씀하시기 바랍니다."
    if conversation_state == "END":
        return "네, 알겠습니다."
    raise ValueError(f"unsupported professor absence state: {conversation_state}")


def _confirmation(state: Dict) -> str:
    class_name = state.get("class_name")
    class_part = f"{class_name} 수업 " if class_name else ""
    return (
        f"{state.get('user_name') or '학생'} 학생, {state.get('absence_date') or '결석 날짜'} "
        f"{class_part}결석 사유가 {state.get('absence_reason') or '결석 사유'}인 것으로 확인했습니다. 맞습니까?"
    )
