from __future__ import annotations

from typing import Dict, List


def get_missing_professor_absence_fields(state: Dict) -> List[str]:
    """
    교수님 결석 사유 전달에 필요한 필수 정보 중 아직 없는 값을 반환한다.

    필수 정보:
    - absence_date: 결석 날짜
    - absence_reason: 결석 사유
    - user_name: 학생 이름

    class_name은 있으면 좋지만, 모든 발화에서 자연스럽게 나오지 않을 수 있어
    MVP에서는 필수값으로 강제하지 않는다.
    """
    missing_fields = []

    if not state.get("absence_date"):
        missing_fields.append("absence_date")

    if not state.get("absence_reason"):
        missing_fields.append("absence_reason")

    if not state.get("user_name"):
        missing_fields.append("user_name")

    return missing_fields


def compact_professor_absence_state(result: Dict) -> Dict:
    """
    클라이언트에 저장할 교수님 결석 사유 전달 상태만 정리한다.
    """
    return {
        "intent": result.get("intent"),
        "professor_name": result.get("professor_name"),
        "class_name": result.get("class_name"),
        "absence_date": result.get("absence_date"),
        "absence_reason": result.get("absence_reason"),
        "user_name": result.get("user_name"),
        "conversation_state": result.get("conversation_state"),
        "missing_fields": result.get("missing_fields") or [],
        "last_ai_message": result.get("ai_message"),
        "user_action": result.get("user_action"),
    }
