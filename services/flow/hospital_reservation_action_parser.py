from __future__ import annotations

from typing import Any, Dict, Optional

from services.flow.reservation_time_utils import select_time_from_options


def parse_hospital_reservation_action(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    병원 예약 시나리오에서 사용자 발화를 user_action으로 변환한다.

    현재 버전은 구조 분리를 위한 1차 parser이다.
    decide_next_state_node가 user_message를 직접 보지 않도록 만드는 것이 목적이다.

    이후 고도화 단계에서 이 함수 내부를 LLM structured output 기반으로 교체할 수 있다.
    """

    user_message = (state.get("user_message") or "").strip()
    conversation_state = state.get("conversation_state") or "greeting"
    alternative_times = state.get("alternative_times") or []

    selected_time = _extract_selected_time(
        user_message=user_message,
        alternative_times=alternative_times,
    )

    user_action = "unknown"

    if conversation_state == "confirming_info":
        user_action = _parse_confirming_info_action(user_message)

    elif conversation_state == "reservation_available":
        user_action = _parse_reservation_available_action(user_message)

    elif conversation_state == "reservation_unavailable":
        user_action = _parse_reservation_unavailable_action(user_message)

    elif conversation_state == "suggest_alternative":
        user_action = _parse_suggest_alternative_action(
            user_message=user_message,
            selected_time=selected_time,
        )

    elif conversation_state == "reservation_confirmed":
        user_action = "go_closing"

    elif conversation_state == "closing":
        user_action = "end_call"

    elif conversation_state == "checking_availability":
        user_action = "lookup_availability"

    return {
        "user_action": user_action,
        "selected_time": selected_time,
    }


def _parse_confirming_info_action(user_message: str) -> str:
    if _contains_any(user_message, ["시간", "몇 시", "오전", "오후"]):
        return "change_time"

    if _contains_any(user_message, ["날짜", "요일", "내일", "모레", "다음"]):
        return "change_date"

    if _contains_any(user_message, ["진료과", "과를", "내과", "피부과", "정형외과", "이비인후과"]):
        return "change_department"

    if _contains_any(user_message, ["네", "맞아요", "맞습니다", "확인", "좋아요", "그대로"]):
        return "confirm_reservation_info"

    return "unknown"


def _parse_reservation_available_action(user_message: str) -> str:
    """
    예약 가능한 시간이 안내된 상태에서 사용자의 행동을 판단한다.

    주의:
    - "네, 그 시간으로 예약하고 싶습니다."는 현재 제안된 시간 확정이다.
    - "그 시간 말고 다른 시간으로요."는 '그 시간'이 포함되어도 변경 요청이다.
    - 따라서 명시적인 거절/변경 표현을 먼저 판단한 뒤, 확정 표현을 판단한다.
    """

    # 먼저 "다른 시간 확인/변경" 의도를 판단한다.
    if _contains_any(user_message, [
        "아니요",
        "다른 시간",
        "다른 시간도",
        "변경",
        "다시",
        "말고",
    ]):
        return "ask_other_time"

    # 그 다음 "제안된 시간으로 예약 진행" 의도를 판단한다.
    if _contains_any(user_message, [
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
    ]):
        return "confirm_available_time"

    return "unknown"


def _parse_reservation_unavailable_action(user_message: str) -> str:
    if _contains_any(user_message, ["다른", "시간", "가능", "언제", "가장 빠른"]):
        return "ask_other_time"

    return "unknown"


def _parse_suggest_alternative_action(
    user_message: str,
    selected_time: Optional[str],
) -> str:
    if selected_time:
        return "select_alternative_time"

    if _contains_any(user_message, ["다른 날짜", "날짜", "내일 말고", "모레"]):
        return "change_date"

    if _contains_any(user_message, ["다른", "시간", "가능"]):
        return "ask_other_time"

    return "unknown"


def _extract_selected_time(
    user_message: str,
    alternative_times: list[str],
) -> Optional[str]:
    # 1. 서버가 제시한 대안 시간 목록에서 먼저 선택 시간을 찾는다.
    selected_from_options = select_time_from_options(
        user_message=user_message,
        time_options=alternative_times,
    )

    if selected_from_options:
        return selected_from_options

    # 2. 대안 목록에 없어도 사용자가 직접 시간대를 말하는 경우를 대비한다.
    if "오전" in user_message:
        return _extract_time_phrase(user_message, "오전")

    if "오후" in user_message:
        return _extract_time_phrase(user_message, "오후")

    return None


def _extract_time_phrase(user_message: str, marker: str) -> Optional[str]:
    """
    예: '오후 4시로 할게요' -> '오후 4시'
    """
    start_index = user_message.find(marker)

    if start_index == -1:
        return None

    sliced = user_message[start_index:]

    for end_token in ["로", "에", "은", "는", "도", " ", ",", "."]:
        token_index = sliced.find(end_token, len(marker))

        if token_index != -1:
            candidate = sliced[:token_index].strip()
            if "시" in candidate:
                return candidate

    # 공백 없이 끝까지 가는 경우
    if "시" in sliced:
        end_index = sliced.find("시") + 1
        return sliced[:end_index].strip()

    return None


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)