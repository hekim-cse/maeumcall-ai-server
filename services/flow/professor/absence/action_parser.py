from __future__ import annotations

from typing import Dict


def parse_professor_absence_action(
    conversation_state: str,
    text: str,
) -> Dict[str, str]:
    """
    교수님 결석 사유 전달 상태에서 사용자 발화를 user_action으로 분류한다.
    """
    text = (text or "").strip()

    if conversation_state == "confirming_absence_info":
        return _parse_confirming_absence_info_action(text)

    if conversation_state == "absence_noted":
        return _parse_absence_noted_action(text)

    if conversation_state == "closing":
        return _parse_closing_action(text)

    return {"user_action": "unknown"}


def _parse_confirming_absence_info_action(text: str) -> Dict[str, str]:
    """
    결석 정보 확인 상태에서 사용자의 확인/수정 의도를 분류한다.
    """
    if _contains_any(text, ["날짜", "오늘", "내일", "요일"]):
        if _is_negative(text):
            return {"user_action": "change_absence_date"}

    if _contains_any(text, ["사유", "이유", "몸", "병원", "개인", "가족"]):
        if _is_negative(text):
            return {"user_action": "change_absence_reason"}

    if _contains_any(text, ["이름", "성함"]):
        if _is_negative(text):
            return {"user_action": "change_user_name"}

    if _is_positive(text):
        return {"user_action": "confirm_absence_info"}

    if _is_negative(text):
        return {"user_action": "change_absence_reason"}

    return {"user_action": "unknown"}


def _parse_absence_noted_action(text: str) -> Dict[str, str]:
    """
    결석 사유 참고 처리 이후 마무리 의도를 분류한다.
    """
    if _contains_any(text, ["감사", "알겠습니다", "확인했습니다", "네", "예"]):
        return {"user_action": "go_closing"}

    return {"user_action": "unknown"}


def _parse_closing_action(text: str) -> Dict[str, str]:
    """
    통화 종료 여부를 판단한다.
    """
    if _contains_any(text, ["감사", "알겠습니다", "네", "예", "좋은 하루"]):
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
            "알겠습니다",
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
            "잘못",
        ],
    )


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)
