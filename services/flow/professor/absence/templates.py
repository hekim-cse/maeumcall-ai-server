from __future__ import annotations

from typing import Dict


def build_professor_absence_template_message(
    conversation_state: str,
    state: Dict,
) -> str:
    """
    LLM 응답이 부적절할 때 사용할 교수님 결석 사유 전달 안전 응답이다.
    """
    professor_name = state.get("professor_name") or "교수님"
    absence_date = state.get("absence_date") or "결석 날짜"
    absence_reason = state.get("absence_reason") or "결석 사유"
    user_name = state.get("user_name") or "학생"
    class_name = state.get("class_name")

    if conversation_state == "collecting_absence_info":
        missing_fields = state.get("missing_fields") or []

        if "absence_date" in missing_fields:
            return f"네, {professor_name}입니다. 결석하게 되는 날짜를 말씀해주시겠습니까?"

        if "absence_reason" in missing_fields:
            return f"{absence_date} 결석으로 확인했습니다. 결석 사유를 말씀해주시겠습니까?"

        if "user_name" in missing_fields:
            return f"{absence_date} 결석 사유는 확인했습니다. 성함을 말씀해주시겠습니까?"

        return _build_confirming_message(state)

    if conversation_state == "confirming_absence_info":
        return _build_confirming_message(state)

    if conversation_state == "absence_noted":
        return (
            f"알겠습니다. {user_name} 학생의 {absence_date} 결석 사유는 "
            "참고하도록 하겠습니다."
        )

    if conversation_state == "closing":
        return "네, 확인했습니다. 추후 필요한 사항이 있으면 다시 말씀하시기 바랍니다."

    if conversation_state == "END":
        return "네, 알겠습니다."

    return f"네, {professor_name}입니다. 결석 사유와 관련해서 말씀해주시겠습니까?"


def _build_confirming_message(state: Dict) -> str:
    absence_date = state.get("absence_date") or "결석 날짜"
    absence_reason = state.get("absence_reason") or "결석 사유"
    user_name = state.get("user_name") or "학생"
    class_name = state.get("class_name")

    class_part = f"{class_name} 수업 " if class_name else ""

    return (
        f"{user_name} 학생, {absence_date} {class_part}결석 사유가 "
        f"{absence_reason}인 것으로 확인했습니다. 맞습니까?"
    )
