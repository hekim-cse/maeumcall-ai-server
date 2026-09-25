from __future__ import annotations

from typing import Any


def format_time_options(time_options: list[str] | None) -> str:
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


def resolve_final_reservation_time(state: dict[str, Any]) -> str | None:
    """
    최종 예약 완료 시 표시할 시간을 결정한다.

    우선순위:
    1. selected_time: 사용자가 대안 시간 중 직접 선택한 시간
    2. available_time: 서버 시뮬레이션이 가능하다고 안내한 시간
    3. time: 사용자가 처음 말한 넓은 시간대
    """
    return state.get("selected_time") or state.get("available_time") or state.get("time")
