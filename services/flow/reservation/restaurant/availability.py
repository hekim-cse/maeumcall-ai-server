from __future__ import annotations

from typing import Dict, List, Optional

from services.flow.reservation.common.availability_provider import (
    AvailabilityProvider,
    AvailabilityQuery,
    get_availability_provider,
)


def resolve_restaurant_availability(
    state: Dict[str, object],
    *,
    provider: Optional[AvailabilityProvider] = None,
) -> Dict[str, object]:
    """
    서버가 소유한 버전 지정 훈련 일정표로 예약 가능 여부를 결정한다.
    """
    date = state.get("date") or "원하시는 날짜"
    time = state.get("time") or "원하시는 시간"
    party_size = state.get("party_size") or "인원"

    decision = (provider or get_availability_provider()).resolve(
        AvailabilityQuery(
            scenario_key="restaurant_reservation",
            requested_time=str(time),
        )
    )
    decision["availability_message_hint"] = _build_restaurant_message(
        decision, str(date), str(time), str(party_size)
    )
    return decision


def _build_restaurant_message(
    decision: Dict[str, Any],
    date: str,
    requested_time: str,
    party_size: str,
) -> str:
    if decision["availability_status"] == "available":
        return (
            f"{date} {decision['available_time']}에 {party_size} 예약이 가능합니다."
        )
    alternatives = decision["alternative_times"]
    if alternatives:
        return (
            f"{date} {requested_time}에는 예약이 어렵습니다. "
            f"대신 {' 또는 '.join(alternatives)}는 가능합니다."
        )
    return f"{date} {requested_time}에는 예약이 어렵습니다."
