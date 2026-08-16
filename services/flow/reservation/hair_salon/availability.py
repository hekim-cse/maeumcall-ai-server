from __future__ import annotations

from typing import Dict, Any, List

from services.flow.reservation.common.availability_contract import (
    validate_availability_result,
)


HAIR_SALON_TRAINING_CONFLICT_SLOTS = {
    "오후 3시": ["오후 2시", "오후 4시"],
    "3시": ["오후 2시", "오후 4시"],
}


def resolve_hair_salon_availability(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    검증된 외부 결과 또는 미용실 통화 훈련 시나리오 정책으로 결과를 결정한다.
    """
    date = state.get("date") or "원하시는 날짜"
    time = state.get("time") or "원하시는 시간"
    service_type = state.get("service_type") or "시술"
    designer = state.get("designer") or "가능한 디자이너"

    simulation_result = state.get("simulation_result")
    if simulation_result is not None:
        decision = validate_availability_result(simulation_result)
        decision["availability_message_hint"] = _build_hair_salon_message(
            decision, date, time, service_type, designer
        )
        decision["reservation_confirmed"] = False
        return decision

    alternative_times: List[str] = HAIR_SALON_TRAINING_CONFLICT_SLOTS.get(time, [])
    if alternative_times:

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


def _build_hair_salon_message(
    decision: Dict[str, Any],
    date: str,
    requested_time: str,
    service_type: str,
    designer: str,
) -> str:
    if decision["availability_status"] == "available":
        return (
            f"{date} {decision['available_time']}에 {designer} 선생님 "
            f"{service_type} 예약이 가능합니다."
        )
    alternatives = decision["alternative_times"]
    if alternatives:
        return (
            f"{date} {requested_time}에는 {designer} 선생님 {service_type} 예약이 어렵습니다. "
            f"대신 {' 또는 '.join(alternatives)}는 가능합니다."
        )
    return f"{date} {requested_time}에는 {designer} 선생님 {service_type} 예약이 어렵습니다."
