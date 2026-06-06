from __future__ import annotations

from typing import Dict, Any, List


def resolve_restaurant_availability(state: dict) -> Dict[str, Any]:
    """
    식당 예약 가능 여부를 시뮬레이션한다.

    실제 외부 예약 시스템 연동 전까지는
    날짜, 시간, 인원 정보를 기반으로 더미 예약 가능 여부를 반환한다.
    """
    date = state.get("date")
    time = state.get("time")
    party_size = state.get("party_size")

    if not date or not time or not party_size:
        return {
            "availability_status": None,
            "availability_reason": "missing_required_info",
            "available_time": None,
            "alternative_times": [],
            "availability_message_hint": None,
            "reservation_confirmed": None,
            "simulation_result": None,
        }

    unavailable_keywords = [
        "7시",
        "저녁 7시",
        "오후 7시",
    ]

    is_unavailable = any(keyword in time for keyword in unavailable_keywords)

    if is_unavailable:
        alternative_times: List[str] = ["저녁 6시", "저녁 8시"]

        return {
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": alternative_times,
            "availability_message_hint": (
                f"{date} {time}에는 예약이 마감되었습니다. "
                f"대신 {' 또는 '.join(alternative_times)}는 가능합니다."
            ),
            "reservation_confirmed": None,
            "simulation_result": {
                "availability_status": "unavailable",
                "availability_reason": "requested_time_full",
                "available_time": None,
                "alternative_times": alternative_times,
            },
        }

    return {
        "availability_status": "available",
        "availability_reason": None,
        "available_time": time,
        "alternative_times": [],
        "availability_message_hint": (
            f"{date} {time}에 {party_size} 예약이 가능합니다."
        ),
        "reservation_confirmed": None,
        "simulation_result": {
            "availability_status": "available",
            "availability_reason": None,
            "available_time": time,
            "alternative_times": [],
        },
    }
