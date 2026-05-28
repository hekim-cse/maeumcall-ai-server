from __future__ import annotations

from typing import Any, Dict, Optional


CONFIRM_RESERVATION_INFO_KEYWORDS = [
    "네",
    "맞아요",
    "맞습니다",
    "확인",
    "좋아요",
    "그대로",
]

CHANGE_TIME_KEYWORDS = [
    "시간",
    "몇 시",
    "오전",
    "오후",
]

CHANGE_DATE_KEYWORDS = [
    "날짜",
    "요일",
    "내일",
    "모레",
    "다음",
    "다른 날짜",
    "내일 말고",
]

CHANGE_DEPARTMENT_KEYWORDS = [
    "진료과",
    "과를",
    "내과",
    "피부과",
    "정형외과",
    "이비인후과",
]

CONFIRM_AVAILABLE_TIME_KEYWORDS = [
    "그 시간으로",
    "그걸로",
    "그 시간",
    "네",
    "좋아요",
    "진행",
    "예약하고 싶",
    "예약해주세요",
    "예약 부탁",
    "맞습니다",
    "해주세요",
]

ASK_OTHER_TIME_KEYWORDS = [
    "아니요",
    "다른 시간",
    "다른 시간도",
    "변경",
    "다시",
    "말고",
]

UNAVAILABLE_ASK_OTHER_TIME_KEYWORDS = [
    "다른",
    "시간",
    "가능",
    "언제",
    "가장 빠른",
]

SUGGEST_ALTERNATIVE_ASK_OTHER_TIME_KEYWORDS = [
    "다른",
    "시간",
    "가능",
]

TIME_MARKERS = [
    "오전",
    "오후",
]

TIME_END_TOKENS = [
    "로",
    "에",
    "은",
    "는",
    "도",
    " ",
    ",",
    ".",
]


def parse_hospital_reservation_action(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    병원 예약 시나리오에서 사용자 발화를 user_action으로 변환한다.

    이 함수의 역할:
    - 현재 conversation_state 기준으로 사용자 의도를 action으로 분류한다.
    - 사용자가 특정 시간을 말한 경우 selected_time 후보를 추출한다.

    주의:
    - selected_time이 실제 예약 가능한 시간인지 검증하지 않는다.
    - selected_time 유효성 검증은 graph의 상태 전이 단계에서 처리한다.
    """

    user_message = (state.get("user_message") or "").strip()
    conversation_state = state.get("conversation_state") or "greeting"
    alternative_times = state.get("alternative_times") or []

    selected_time = extract_selected_time(
        user_message=user_message,
        alternative_times=alternative_times,
    )

    user_action = parse_action_by_state(
        conversation_state=conversation_state,
        user_message=user_message,
        selected_time=selected_time,
    )

    return {
        "user_action": user_action,
        "selected_time": selected_time,
    }


def parse_action_by_state(
    conversation_state: str,
    user_message: str,
    selected_time: Optional[str],
) -> str:
    if conversation_state == "confirming_info":
        return parse_confirming_info_action(user_message)

    if conversation_state == "reservation_available":
        return parse_reservation_available_action(user_message)

    if conversation_state == "reservation_unavailable":
        return parse_reservation_unavailable_action(user_message)

    if conversation_state == "suggest_alternative":
        return parse_suggest_alternative_action(
            user_message=user_message,
            selected_time=selected_time,
        )

    if conversation_state == "reservation_confirmed":
        return "go_closing"

    if conversation_state == "closing":
        return "end_call"

    if conversation_state == "checking_availability":
        return "lookup_availability"

    return "unknown"


def parse_confirming_info_action(user_message: str) -> str:
    if contains_any(user_message, CHANGE_TIME_KEYWORDS):
        return "change_time"

    if contains_any(user_message, CHANGE_DATE_KEYWORDS):
        return "change_date"

    if contains_any(user_message, CHANGE_DEPARTMENT_KEYWORDS):
        return "change_department"

    if contains_any(user_message, CONFIRM_RESERVATION_INFO_KEYWORDS):
        return "confirm_reservation_info"

    return "unknown"


def parse_reservation_available_action(user_message: str) -> str:
    """
    예약 가능한 시간이 안내된 상태에서 사용자 행동을 판단한다.

    예:
    - "네, 그 시간으로 예약하고 싶습니다." → confirm_available_time
    - "그 시간 말고 다른 시간으로요." → ask_other_time

    따라서 명시적인 거절/변경 표현을 먼저 검사한다.
    """

    if contains_any(user_message, ASK_OTHER_TIME_KEYWORDS):
        return "ask_other_time"

    if contains_any(user_message, CONFIRM_AVAILABLE_TIME_KEYWORDS):
        return "confirm_available_time"

    return "unknown"


def parse_reservation_unavailable_action(user_message: str) -> str:
    """
    예약 불가 상태에서 사용자 행동을 판단한다.

    예:
    - "다른 날짜로 확인해주세요." → change_date
    - "다른 시간도 가능할까요?" → ask_other_time

    날짜 변경 표현은 "다른"이라는 단어를 포함할 수 있으므로,
    다른 시간 요청보다 먼저 검사한다.
    """

    if contains_any(user_message, CHANGE_DATE_KEYWORDS):
        return "change_date"

    if contains_any(user_message, UNAVAILABLE_ASK_OTHER_TIME_KEYWORDS):
        return "ask_other_time"

    return "unknown"


def parse_suggest_alternative_action(
    user_message: str,
    selected_time: Optional[str],
) -> str:
    if selected_time:
        return "select_alternative_time"

    if contains_any(user_message, CHANGE_DATE_KEYWORDS):
        return "change_date"

    if contains_any(user_message, SUGGEST_ALTERNATIVE_ASK_OTHER_TIME_KEYWORDS):
        return "ask_other_time"

    return "unknown"


def extract_selected_time(
    user_message: str,
    alternative_times: list[str],
) -> Optional[str]:
    for alternative_time in alternative_times:
        if alternative_time and alternative_time in user_message:
            return alternative_time

    for marker in TIME_MARKERS:
        if marker in user_message:
            return extract_time_phrase(user_message, marker)

    return None


def extract_time_phrase(user_message: str, marker: str) -> Optional[str]:
    """
    예:
    - '오후 4시로 할게요' → '오후 4시'
    - '오후 5시는 가능할까요?' → '오후 5시'
    """

    start_index = user_message.find(marker)

    if start_index == -1:
        return None

    sliced = user_message[start_index:]

    for end_token in TIME_END_TOKENS:
        token_index = sliced.find(end_token, len(marker))

        if token_index != -1:
            candidate = sliced[:token_index].strip()
            if "시" in candidate:
                return candidate

    if "시" in sliced:
        end_index = sliced.find("시") + 1
        return sliced[:end_index].strip()

    return None


def contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)
