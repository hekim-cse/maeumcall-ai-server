from __future__ import annotations

from typing import Dict, Any, List


def resolve_hair_salon_availability(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    미용실 예약 가능 여부를 시뮬레이션한다.

    현재는 실제 예약 시스템이 없으므로 테스트 가능한 규칙 기반으로 처리한다.

    기본 정책:
    - 오후 3시 / 3시는 인기 시간대로 가정하여 마감 처리한다.
    - 그 외 시간은 예약 가능으로 처리한다.
    - 마감된 경우 대안 시간으로 오후 2시, 오후 4시를 제안한다.
    """
    date = state.get("date") or "원하시는 날짜"
    time = state.get("time") or "원하시는 시간"
    service_type = state.get("service_type") or "시술"
    designer = state.get("designer") or "가능한 디자이너"

    unavailable_times = {
        "오후 3시",
        "3시",
    }

    if time in unavailable_times:
        alternative_times: List[str] = ["오후 2시", "오후 4시"]

        return {
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": alternative_times,
            "availability_message_hint": (
                f"{date} {time}에는 {designer} 선생님 {service_type} 예약이 어렵습니다. "
                f"대신 {' 또는 '.join(alternative_times)}는 가능합니다."
            ),
            "reservation_confirmed": False,
        }

    return {
        "availability_status": "available",
        "availability_reason": None,
        "available_time": time,
        "alternative_times": [],
        "availability_message_hint": (
            f"{date} {time}에 {designer} 선생님 {service_type} 예약이 가능합니다."
        ),
        "reservation_confirmed": False,
    }
