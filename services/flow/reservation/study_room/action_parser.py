from __future__ import annotations

import re
from typing import Dict, Optional


def parse_study_room_reservation_action(
    conversation_state: str,
    user_message: str,
    state: dict = None,
) -> Dict[str, Optional[str]]:
    """
    스터디룸 예약 흐름에서 사용자의 응답 의도를 해석한다.

    LangGraph는 상태 전이와 조건 분기를 담당하고,
    실제 응답 문장은 LLM이 생성한다.
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
    if _is_negative(text):
        return {"user_action": "unknown"}

    return {"user_action": "continue_collecting"}


def _parse_confirming_info_action(text: str) -> Dict[str, Optional[str]]:
    """
    예약 정보 확인 상태에서 사용자가 확인/변경 의도를 말했는지 판단한다.
    """

    # 변경 의도는 긍정 표현보다 먼저 판단한다.
    if _contains_any(text, ["이름", "성함", "예약자"]):
        return {"user_action": "change_user_name"}

    if _contains_any(text, ["날짜", "내일", "모레", "오늘", "주말"]):
        return {"user_action": "change_date"}

    # "시작 시간"은 이용 시간과 다르므로 먼저 분리해서 판단한다.
    if _contains_any(text, ["시작 시간", "시작시간", "몇 시부터", "몇시부터", "시작"]):
        return {"user_action": "change_start_time"}

    # "이용 시간"은 몇 시간 이용할지에 대한 값이다.
    if _contains_any(text, ["이용 시간", "이용시간", "몇 시간", "몇시간", "두 시간", "세 시간"]):
        return {"user_action": "change_duration"}

    if _contains_any(text, ["시간 바꾸", "시간 변경"]):
        return {"user_action": "change_start_time"}

    if _contains_any(text, ["인원", "명", "분", "사람"]):
        return {"user_action": "change_party_size"}

    if _is_negative(text):
        return {"user_action": "change_info"}

    if _is_positive(text):
        return {"user_action": "confirm"}

    return {"user_action": "unknown"}


def _parse_reservation_available_action(text: str) -> Dict[str, Optional[str]]:
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


def _extract_selected_time(text: str) -> Optional[str]:
    korean_number_map = {
        "한": "1",
        "두": "2",
        "세": "3",
        "네": "4",
        "다섯": "5",
        "여섯": "6",
        "일곱": "7",
        "여덟": "8",
        "아홉": "9",
        "열": "10",
    }

    match = re.search(r"(오전|오후|저녁|밤)\s*(\d{1,2})\s*시", text)
    if match:
        return f"{match.group(1)} {match.group(2)}시"

    for korean, number in korean_number_map.items():
        match = re.search(fr"(오전|오후|저녁|밤)\s*{korean}\s*시", text)
        if match:
            return f"{match.group(1)} {number}시"

    match = re.search(r"(\d{1,2})\s*시", text)
    if match:
        return f"{match.group(1)}시"

    return None


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
