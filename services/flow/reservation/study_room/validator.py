from __future__ import annotations


def is_valid_study_room_response(conversation_state: str, text: str) -> bool:
    """
    스터디룸 예약 상태에 맞는 LLM 응답인지 최소 검증한다.
    """
    text = (text or "").strip()

    if not text:
        return False

    if conversation_state == "collecting_reservation_info":
        return any(
            keyword in text
            for keyword in ["예약", "날짜", "시간", "몇 분", "성함", "이용"]
        )

    if conversation_state == "confirming_info":
        return "예약" in text and any(keyword in text for keyword in ["맞", "확인"])

    if conversation_state == "checking_availability":
        return any(keyword in text for keyword in ["확인", "잠시", "기다려"])

    if conversation_state == "reservation_available":
        return "가능" in text

    if conversation_state == "reservation_unavailable":
        # 예약 불가 상태에서는 반드시 불가 의미가 포함되어야 한다.
        # "대신", "가능"만 있으면 예약 가능 안내처럼 보일 수 있으므로 통과시키지 않는다.
        return any(
            keyword in text
            for keyword in ["어렵", "어려운", "마감", "불가능", "불가"]
        )

    if conversation_state == "reservation_confirmed":
        return "예약" in text and any(keyword in text for keyword in ["완료", "확정"])

    if conversation_state == "closing":
        return any(keyword in text for keyword in ["감사", "좋은 하루", "이용"])

    if conversation_state == "END":
        return any(keyword in text for keyword in ["감사", "좋은 하루"])

    return True
