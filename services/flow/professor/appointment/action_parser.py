from __future__ import annotations

from typing import Dict


def parse_professor_appointment_action(
    conversation_state: str,
    text: str,
) -> Dict[str, str]:
    """
    교수님 면담 예약 상태에서 사용자 발화를 user_action으로 분류한다.
    """
    text = (text or "").strip()

    if conversation_state == "confirming_info":
        return _parse_confirming_info_action(text)

    if conversation_state == "appointment_confirmed":
        return _parse_appointment_confirmed_action(text)

    if conversation_state == "closing":
        return _parse_closing_action(text)

    return {"user_action": "unknown"}


def _parse_confirming_info_action(text: str) -> Dict[str, str]:
    """
    면담 정보 확인 상태에서 사용자의 확인/변경 요청을 분류한다.
    """
    if _contains_any(text, ["목적", "내용", "사유", "이유", "다시"]):
        return {"user_action": "change_appointment_purpose"}

    if _contains_any(text, ["날짜", "요일", "오늘", "내일", "모레", "이번 주", "다음 주"]):
        return {"user_action": "change_date"}

    if _contains_any(text, ["시간", "오전", "오후", "몇 시", "몇시"]):
        return {"user_action": "change_time"}

    if _contains_any(text, ["이름", "성함", "학생", "학번"]):
        return {"user_action": "change_user_name"}

    if _is_positive(text):
        return {"user_action": "confirm"}

    if _is_negative(text):
        return {"user_action": "change_info"}

    return {"user_action": "unknown"}


def _parse_appointment_confirmed_action(text: str) -> Dict[str, str]:
    """
    면담 일정 확인 이후 마무리 이동 여부를 판단한다.
    """
    if _contains_any(text, ["감사", "알겠습니다", "확인했습니다", "네"]):
        return {"user_action": "go_closing"}

    return {"user_action": "unknown"}


def _parse_closing_action(text: str) -> Dict[str, str]:
    """
    통화 종료 여부를 판단한다.
    """
    if _contains_any(text, ["감사", "알겠습니다", "네", "좋은 하루"]):
        return {"user_action": "end_call"}

    return {"user_action": "unknown"}


def _is_positive(text: str) -> bool:
    return _contains_any(
        text,
        [
            "네",
            "예",
            "맞습니다",
            "맞아요",
            "그렇습니다",
            "확인했습니다",
            "괜찮습니다",
            "가능합니다",
            "부탁드립니다",
        ],
    )


def _is_negative(text: str) -> bool:
    return _contains_any(
        text,
        [
            "아니요",
            "아닙니다",
            "수정",
            "변경",
            "바꾸",
            "다시",
            "어렵습니다",
        ],
    )


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)
