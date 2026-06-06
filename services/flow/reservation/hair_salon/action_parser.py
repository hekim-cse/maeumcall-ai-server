from __future__ import annotations

from typing import Dict, Optional


def parse_hair_salon_reservation_action(
    conversation_state: str,
    user_message: str,
    state: dict = None,
) -> Dict[str, Optional[str]]:
    """
    미용실 예약 흐름에서 사용자의 응답 의도를 해석한다.

    LLM을 쓰지 않고 현재 상태와 사용자 발화를 기반으로
    예약 확인, 변경, 확정, 종료 행동을 판단한다.
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
    """
    확인 상태에서는 변경 의도를 긍정보다 먼저 판단한다.

    예:
    - "예약자 이름을 바꾸고 싶어요." 안에는 "예"가 포함될 수 있으므로
      긍정을 먼저 보면 confirm으로 오분류될 수 있다.
    """
    if _contains_any(text, ["디자이너", "선생님", "쌤", "담당"]):
        return {"user_action": "change_designer"}

    if _contains_any(text, ["시술", "커트", "컷", "펌", "파마", "염색", "클리닉"]):
        return {"user_action": "change_service_type"}

    if _contains_any(text, ["이름", "성함", "예약자"]):
        return {"user_action": "change_user_name"}

    if _contains_any(text, ["시간", "몇 시"]):
        return {"user_action": "change_time"}

    if _contains_any(text, ["날짜", "내일", "모레", "오늘", "주말"]):
        return {"user_action": "change_date"}

    if _is_negative(text):
        return {"user_action": "change_info"}

    if _is_positive(text):
        return {"user_action": "confirm"}

    return {"user_action": "unknown"}


def _parse_reservation_available_action(text: str) -> Dict[str, Optional[str]]:
    """
    예약 가능 안내 후 사용자의 확정/변경 의도를 판단한다.
    """
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
    """
    예약 불가 안내 후 대안 시간 선택, 다른 시간 요청, 날짜 변경을 판단한다.
    """
    selected_time = _extract_selected_time(text)

    if selected_time:
        return {
            "user_action": "select_alternative_time",
            "selected_time": selected_time,
        }

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



def _extract_selected_time(text: str) -> Optional[str]:
    """
    예약 불가 상태에서 사용자가 선택한 대안 시간을 추출한다.
    """
    time_patterns = [
        "오전 10시",
        "오전 11시",
        "오후 1시",
        "오후 2시",
        "오후 3시",
        "오후 4시",
        "오후 5시",
        "오후 6시",
        "10시",
        "11시",
        "1시",
        "2시",
        "3시",
        "4시",
        "5시",
        "6시",
    ]

    for time in time_patterns:
        if time in text:
            return time

    return None
