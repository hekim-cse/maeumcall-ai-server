from __future__ import annotations

from typing import Dict, Any, List


def resolve_study_room_availability(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    스터디룸 예약 가능 여부를 시뮬레이션한다.

    실제 예약 시스템 연동 전까지는 규칙 기반으로 판단한다.

    기본 정책:
    - 오후 2시는 인기 시간대로 가정하여 마감 처리한다.
    - 그 외 시간은 예약 가능 처리한다.
    - 마감된 경우 대안 시간으로 오후 1시, 오후 3시를 제안한다.
    """
    date = state.get("date") or "원하시는 날짜"
    start_time = state.get("start_time") or "원하시는 시간"
    duration = state.get("duration") or "이용 시간"
    party_size = state.get("party_size") or "인원"

    unavailable_times = {
        "오후 2시",
        "2시",
    }

    if start_time in unavailable_times:
        alternative_times: List[str] = ["오후 1시", "오후 3시"]

        return {
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": alternative_times,
            "availability_message_hint": (
                f"{date} {start_time}부터는 예약이 어렵습니다. "
                f"대신 {' 또는 '.join(alternative_times)}부터는 가능합니다."
            ),
            "reservation_confirmed": False,
        }

    return {
        "availability_status": "available",
        "availability_reason": None,
        "available_time": start_time,
        "alternative_times": [],
        "availability_message_hint": (
            f"{date} {start_time}부터 {duration}, {party_size} 이용 예약이 가능합니다."
        ),
        "reservation_confirmed": False,
    }
