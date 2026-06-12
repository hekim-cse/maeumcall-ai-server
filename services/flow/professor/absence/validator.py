from __future__ import annotations

from services.flow.common.tone_validator import has_too_casual_tone


def is_valid_professor_absence_response(
    conversation_state: str,
    text: str,
) -> bool:
    """
    교수님 결석 사유 전달 응답이 현재 상태와 말투 기준에 맞는지 검증한다.
    """
    text = (text or "").strip()

    if not text:
        return False

    if has_too_casual_tone(text):
        return False

    if conversation_state == "collecting_absence_info":
        return any(
            keyword in text
            for keyword in ["결석", "사유", "날짜", "성함", "말씀", "확인"]
        )

    if conversation_state == "confirming_absence_info":
        return any(keyword in text for keyword in ["확인", "맞", "결석", "사유"])

    if conversation_state == "absence_noted":
        return any(keyword in text for keyword in ["알겠습니다", "확인", "참고", "결석"])

    if conversation_state == "closing":
        return any(keyword in text for keyword in ["확인", "알겠습니다", "말씀"])

    if conversation_state == "END":
        return any(keyword in text for keyword in ["알겠습니다", "확인"])

    return True

