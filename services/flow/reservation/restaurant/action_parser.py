from __future__ import annotations

from typing import Dict, Optional


def parse_restaurant_reservation_action(
    conversation_state: str,
    user_message: str,
    state: dict = None,
) -> Dict[str, Optional[str]]:
    """
    식당 예약 흐름에서 사용자의 응답 의도를 해석한다.

    이 함수는 LLM을 쓰지 않고,
    현재 상태와 사용자 발화를 기반으로 다음 행동을 결정한다.
    """
    state = state or {}
    text = (user_message or "").strip()

    if not text:
        return {"user_action": "unknown"}

    if conversation_state == "collecting_reservation_info":
        return _parse_collecting_info_action(text)

    if conversation_state == "confirming_info":
        return _parse_confirming_info_action(text)

    if conversation_state == "reservation_available":
        return _parse_reservation_available_action(text)

    if conversation_state == "reservation_unavailable":
        return _parse_reservation_unavailable_action(text)

    if conversation_state == "reservation_confirmed":
        return _parse_reservation_confirmed_action(text)

    if conversation_state == "closing":
        return _parse_closing_action(text)

    return {"user_action": "unknown"}


def _parse_collecting_info_action(text: str) -> Dict[str, Optional[str]]:
    """
    정보 수집 중에는 사용자가 추가 정보를 말하는 경우가 많으므로
    기본적으로 continue_collecting으로 처리한다.
    """
    if _is_negative(text):
        return {"user_action": "unknown"}

    return {"user_action": "continue_collecting"}


def _parse_confirming_info_action(text: str) -> Dict[str, Optional[str]]:
    # 변경 의도는 긍정 표현보다 먼저 판단한다.
    # 예: "예약자 이름을 바꾸고 싶어요." 안에는 "예"가 포함되어 있으므로
    # 긍정을 먼저 보면 confirm으로 오분류될 수 있다.
    if _contains_any(text, ["이름", "성함", "예약자"]):
        return {"user_action": "change_user_name"}

    if _contains_any(text, ["시간", "몇 시"]):
        return {"user_action": "change_time"}

    if _contains_any(text, ["날짜", "내일", "모레", "오늘", "주말"]):
        return {"user_action": "change_date"}

    if _contains_any(text, ["인원", "명", "분", "사람"]):
        return {"user_action": "change_party_size"}

    if _is_negative(text):
        return {"user_action": "change_info"}

    if _is_positive(text):
        return {"user_action": "confirm"}

    return {"user_action": "unknown"}


def _parse_reservation_available_action(text: str) -> Dict[str, Optional[str]]:
    # 다른 시간/날짜 요청은 긍정 표현보다 먼저 판단한다.
    # 예: "그 시간 말고 다른 시간 가능할까요?" 안에는 "그 시간"이 포함되어 있으므로
    # 긍정을 먼저 보면 confirm_reservation으로 오분류될 수 있다.
    if _contains_any(text, ["다른 날짜", "날짜 바꾸", "날짜 변경"]):
        return {"user_action": "change_date"}

    if _contains_any(text, ["다른 시간", "다른 시간대", "말고", "변경", "바꾸"]):
        return {"user_action": "ask_other_time"}

    if _is_negative(text):
        return {"user_action": "ask_other_time"}

    if _is_positive(text):
        return {"user_action": "confirm_reservation"}

    return {"user_action": "unknown"}


def _parse_reservation_unavailable_action(text: str) -> Dict[str, Optional[str]]:
    if _contains_any(text, ["다른 시간", "다른 시간대", "가능한 시간", "가장 빠른"]):
        return {"user_action": "ask_other_time"}

    if _contains_any(text, ["다른 날짜", "날짜", "내일", "모레", "주말"]):
        return {"user_action": "change_date"}

    if _is_positive(text):
        return {"user_action": "ask_other_time"}

    return {"user_action": "unknown"}


def _parse_reservation_confirmed_action(text: str) -> Dict[str, Optional[str]]:
    if _contains_any(text, ["감사", "네", "예", "확인"]):
        return {"user_action": "go_closing"}

    return {"user_action": "unknown"}


def _parse_closing_action(text: str) -> Dict[str, Optional[str]]:
    if _contains_any(text, ["감사", "네", "예", "괜찮", "없습니다"]):
        return {"user_action": "end_call"}

    return {"user_action": "unknown"}


def _is_positive(text: str) -> bool:
    return _contains_any(
        text,
        [
            "네",
            "예",
            "맞아요",
            "맞습니다",
            "좋아요",
            "좋습니다",
            "괜찮아요",
            "괜찮습니다",
            "그걸로",
            "그 시간",
            "예약해주세요",
            "예약해 주세요",
            "진행해주세요",
            "진행해 주세요",
        ],
    )


def _is_negative(text: str) -> bool:
    return _contains_any(
        text,
        [
            "아니요",
            "아뇨",
            "아니",
            "말고",
            "어려워요",
            "안 돼요",
            "안됩니다",
            "힘들어요",
            "바꾸고",
            "변경",
        ],
    )


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)
