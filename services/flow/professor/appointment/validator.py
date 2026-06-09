from __future__ import annotations


def is_valid_professor_appointment_response(
    conversation_state: str,
    text: str,
) -> bool:
    """
    교수님 면담 예약 응답이 현재 상태와 말투 기준에 맞는지 검증한다.
    """
    text = (text or "").strip()

    if not text:
        return False

    if _has_too_casual_tone(text):
        return False

    if conversation_state == "collecting_appointment_info":
        return any(
            keyword in text
            for keyword in ["면담", "목적", "날짜", "시간", "성함", "말씀", "확인"]
        )

    if conversation_state == "confirming_info":
        return any(keyword in text for keyword in ["확인", "맞", "희망", "면담"])

    if conversation_state == "closing":
        return any(keyword in text for keyword in ["확인", "알겠습니다", "참고"])

    if conversation_state == "END":
        return any(keyword in text for keyword in ["알겠습니다", "확인"])

    return True


def _has_too_casual_tone(text: str) -> bool:
    casual_words = [
        "ㅋㅋ",
        "ㅎㅎ",
        "응",
        "그래",
        "오케이",
        "넵",
        "좋아",
        "말해줘",
        "괜찮아",
    ]

    return any(word in text for word in casual_words)
