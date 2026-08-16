from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.flow.reservation.common.availability_contract import (
    validate_availability_result,
)


HOSPITAL_TRAINING_TIME_SLOTS = {
    "오전": "오전 10시",
    "오후": "오후 3시",
}


def resolve_hospital_availability(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    검증된 외부 결과 또는 병원 통화 훈련 시나리오 정책으로 결과를 결정한다.
    """

    department = state.get("department") or "진료과"
    date = state.get("date") or "원하시는 날짜"
    time = state.get("time") or "원하시는 시간대"

    simulation_result = state.get("simulation_result")

    if simulation_result is not None:
        decision = validate_availability_result(simulation_result)
        status = decision["availability_status"]
        reason = decision["availability_reason"]
        available_time = decision["available_time"]
        alternative_times = decision["alternative_times"]

        return {
            "availability_status": status,
            "availability_reason": reason,
            "available_time": available_time,
            "alternative_times": alternative_times,
            "availability_message_hint": build_availability_message_hint(
                department=department,
                date=date,
                time=time,
                status=status,
                reason=reason,
                available_time=available_time,
                alternative_times=alternative_times,
            ),
        }

    available_time = HOSPITAL_TRAINING_TIME_SLOTS.get(time, time)

    return {
        "availability_status": "available",
        "availability_reason": None,
        "available_time": available_time,
        "alternative_times": [],
        "availability_message_hint": f"{date} {available_time}에 {department} 진료 예약이 가능합니다.",
    }


def build_availability_message_hint(
    department: str,
    date: str,
    time: str,
    status: str,
    reason: Optional[str],
    available_time: Optional[str],
    alternative_times: List[str],
) -> str:
    if status == "available":
        safe_time = available_time or time
        return f"{date} {safe_time}에 {department} 진료 예약이 가능합니다."

    if reason == "requested_time_full":
        alternatives = format_alternative_times(alternative_times)
        return f"{date} {time}에는 예약이 모두 차 있습니다. 대신 {alternatives} 시간대는 가능합니다."

    if reason == "doctor_unavailable":
        alternatives = format_alternative_times(alternative_times)
        return f"{date} {time}에는 담당 의사 진료가 없습니다. 대신 {alternatives} 예약이 가능합니다."

    if reason == "hospital_closed":
        alternatives = format_alternative_times(alternative_times)
        return f"{date}에는 병원 휴무로 예약이 어렵습니다. 대신 {alternatives} 예약이 가능합니다."

    alternatives = format_alternative_times(alternative_times)
    return f"{date} {time}에는 예약이 어렵습니다. 대신 {alternatives} 예약이 가능합니다."


def format_alternative_times(alternative_times: List[str]) -> str:
    if not alternative_times:
        return "다른 시간대"

    if len(alternative_times) == 1:
        return alternative_times[0]

    return " 또는 ".join(alternative_times)
