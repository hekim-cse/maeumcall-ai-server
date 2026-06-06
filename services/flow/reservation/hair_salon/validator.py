from __future__ import annotations


def is_valid_hair_salon_ai_message(
    conversation_state: str,
    ai_message: str,
) -> bool:
    """
    미용실 예약 상태에 맞는 응답인지 최소 검증한다.

    LLM을 우선 사용하되,
    상태와 맞지 않는 응답이면 template fallback을 사용하기 위한 방어 로직이다.
    """
    text = (ai_message or "").strip()

    if not text:
        return False

    if len(text) > 180:
        return False

    if conversation_state == "collecting_reservation_info":
        return any(
            keyword in text
            for keyword in ["예약", "날짜", "시간", "시술", "디자이너", "성함", "방문"]
        )

    if conversation_state == "confirming_info":
        return "예약" in text and any(
            keyword in text
            for keyword in ["맞으실까요", "맞을까요", "확인"]
        )

    if conversation_state == "checking_availability":
        return any(
            keyword in text
            for keyword in ["확인", "잠시", "가능 여부", "예약 가능한지"]
        )

    if conversation_state == "reservation_available":
        # 예약 가능 상태에서는 아직 확정이 아니라 가능 여부 안내여야 한다.
        return "가능" in text

    if conversation_state == "reservation_unavailable":
        # 예약 불가 상태에서는 반드시 불가 표현이 있어야 한다.
        return any(
            keyword in text
            for keyword in ["어렵", "어려운", "마감", "불가능", "힘들"]
        )

    if conversation_state == "reservation_confirmed":
        return "예약" in text and any(
            keyword in text
            for keyword in ["완료", "확정", "잡아"]
        )

    if conversation_state == "closing":
        return any(keyword in text for keyword in ["감사", "방문", "좋은 하루"])

    if conversation_state == "END":
        return any(keyword in text for keyword in ["감사", "좋은 하루"])

    return True
