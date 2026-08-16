from __future__ import annotations

from typing import Dict, Any, List

from services.flow.reservation.common.availability_contract import (
    validate_availability_result,
)


STUDY_ROOM_TRAINING_CONFLICT_SLOTS = {
    "오후 2시": ["오후 1시", "오후 3시"],
    "2시": ["오후 1시", "오후 3시"],
}


def resolve_study_room_availability(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    검증된 외부 결과 또는 스터디룸 통화 훈련 시나리오 정책으로 결과를 결정한다.
    """
    date = state.get("date") or "원하시는 날짜"
    start_time = state.get("start_time") or "원하시는 시간"
    duration = state.get("duration") or "이용 시간"
    party_size = state.get("party_size") or "인원"

    simulation_result = state.get("simulation_result")
    if simulation_result is not None:
        decision = validate_availability_result(simulation_result)
        decision["availability_message_hint"] = _build_study_room_message(
            decision, date, start_time, duration, party_size
        )
        decision["reservation_confirmed"] = False
        return decision

    alternative_times: List[str] = STUDY_ROOM_TRAINING_CONFLICT_SLOTS.get(
        start_time, []
    )
    if alternative_times:

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


def _build_study_room_message(
    decision: Dict[str, Any],
    date: str,
    requested_time: str,
    duration: str,
    party_size: str,
) -> str:
    if decision["availability_status"] == "available":
        return (
            f"{date} {decision['available_time']}부터 {duration}, "
            f"{party_size} 이용 예약이 가능합니다."
        )
    alternatives = decision["alternative_times"]
    if alternatives:
        return (
            f"{date} {requested_time}부터는 예약이 어렵습니다. "
            f"대신 {' 또는 '.join(alternatives)}부터는 가능합니다."
        )
    return f"{date} {requested_time}부터는 예약이 어렵습니다."
