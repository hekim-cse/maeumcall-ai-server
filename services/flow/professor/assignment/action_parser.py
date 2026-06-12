from __future__ import annotations

from typing import Dict


def parse_professor_assignment_action(
    conversation_state: str,
    text: str,
) -> Dict[str, str]:
    """
    교수님 과제 문의 상태에서 사용자 발화를 user_action으로 분류한다.
    """
    text = (text or "").strip()

    if conversation_state == "answering_assignment_question":
        return _parse_answering_assignment_question_action(text)

    if conversation_state == "closing":
        return _parse_closing_action(text)

    return {"user_action": "unknown"}


def _parse_answering_assignment_question_action(text: str) -> Dict[str, str]:
    """
    과제 문의 답변 이후 사용자의 추가 질문/마무리 의도를 분류한다.
    """
    if _contains_any(text, ["추가", "하나 더", "더 여쭤", "다른 질문", "질문드려도"]):
        return {"user_action": "ask_follow_up"}

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


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)
