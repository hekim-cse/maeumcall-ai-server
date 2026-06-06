from __future__ import annotations


def validate_restaurant_reservation_message(
    conversation_state: str,
    message: str,
) -> bool:
    """
    식당 예약 상태에 맞는 응답인지 최소 검증한다.

    LLM 응답을 그대로 쓰면 상태와 맞지 않는 말이 나올 수 있으므로,
    상태별 금지/필수 조건을 가볍게 확인한다.
    """
    text = (message or "").strip()

    if not text:
        return False

    banned_tokens = ["assistant", "user", "```", "{", "}", "[", "]"]
    if any(token in text for token in banned_tokens):
        return False

    if len(text) > 160:
        return False

    if conversation_state == "collecting_reservation_info":
        return any(
            keyword in text
            for keyword in ["예약", "날짜", "시간", "몇 분", "성함", "방문"]
        )

    if conversation_state == "confirming_info":
        return any(
            keyword in text
            for keyword in ["맞으실까요", "맞을까요", "확인"]
        )

    if conversation_state == "reservation_available":
        # 예약 가능 상태에서는 사용자가 가능한 시간임을 명확히 알 수 있어야 한다.
        # LLM이 "예약해드리겠습니다"처럼 확정처럼 말하면 상태 흐름과 어긋날 수 있으므로
        # "가능" 표현을 필수로 둔다.
        return "가능" in text

    if conversation_state == "reservation_unavailable":
        # 예약 불가 상태에서는 반드시 불가 표현이 있어야 한다.
        # "대신", "가능"만 있으면 LLM이 예약 가능처럼 말해도 통과할 수 있으므로 제외한다.
        return any(
            keyword in text
            for keyword in ["어렵", "마감", "불가", "어려운"]
        )

    if conversation_state == "reservation_confirmed":
        return "예약" in text and any(keyword in text for keyword in ["완료", "확정"])

    if conversation_state in ["closing", "END"]:
        return any(keyword in text for keyword in ["감사", "좋은 하루", "방문"])

    return True
