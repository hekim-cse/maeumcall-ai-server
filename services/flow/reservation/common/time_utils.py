from __future__ import annotations

from typing import Optional, List, Dict, Any


def normalize_time_text(value: Optional[str]) -> Optional[str]:
    """
    시간 문자열 비교를 위해 공백을 제거한다.

    예:
    - "오후 4시" -> "오후4시"
    - " 오후 4시 " -> "오후4시"
    """
    if not value:
        return None

    return value.strip().replace(" ", "")


def is_same_time(left: Optional[str], right: Optional[str]) -> bool:
    """
    두 시간 표현이 같은지 비교한다.
    """
    normalized_left = normalize_time_text(left)
    normalized_right = normalize_time_text(right)

    if not normalized_left or not normalized_right:
        return False

    return normalized_left == normalized_right


def is_time_in_options(
    selected_time: Optional[str],
    time_options: Optional[List[str]],
) -> bool:
    """
    선택한 시간이 가능한 시간 목록 안에 있는지 확인한다.
    """
    if not selected_time:
        return False

    return any(
        is_same_time(selected_time, option)
        for option in (time_options or [])
    )


def format_time_options(time_options: Optional[List[str]]) -> str:
    """
    가능한 시간 목록을 사용자에게 보여줄 문자열로 변환한다.

    예:
    - ["오후 4시"] -> "오후 4시"
    - ["오후 4시", "오후 5시"] -> "오후 4시 또는 오후 5시"
    """
    options = [time for time in (time_options or []) if time]

    if not options:
        return "다른 시간대"

    if len(options) == 1:
        return options[0]

    return " 또는 ".join(options)


def resolve_final_reservation_time(state: Dict[str, Any]) -> Optional[str]:
    """
    최종 예약 완료 시 표시할 시간을 결정한다.

    우선순위:
    1. selected_time: 사용자가 대안 시간 중 직접 선택한 시간
    2. available_time: 서버 시뮬레이션이 가능하다고 안내한 시간
    3. time: 사용자가 처음 말한 넓은 시간대
    """
    return (
        state.get("selected_time")
        or state.get("available_time")
        or state.get("time")
    )


def select_time_from_options(
    user_message: str,
    time_options: Optional[List[str]],
) -> Optional[str]:
    """
    사용자 발화 안에 가능한 시간 목록 중 하나가 포함되어 있는지 확인한다.
    """
    message = user_message or ""

    for option in (time_options or []):
        if option and option in message:
            return option

        if option and normalize_time_text(option) in normalize_time_text(message):
            return option

    return None