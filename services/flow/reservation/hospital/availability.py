from __future__ import annotations

from services.flow.reservation.common.availability_provider import (
    AvailabilityProvider,
    AvailabilityQuery,
    get_availability_provider,
)


def resolve_hospital_availability(
    state: dict[str, object],
    *,
    provider: AvailabilityProvider | None = None,
) -> dict[str, object]:
    """
    서버가 소유한 버전 지정 훈련 일정표로 예약 가능 여부를 결정한다.
    """

    department = state.get("department") or "진료과"
    date = state.get("date") or "원하시는 날짜"
    time = state.get("time") or "원하시는 시간대"

    decision = (provider or get_availability_provider()).resolve(
        AvailabilityQuery(
            scenario_key="hospital_reservation",
            requested_time=str(time),
        )
    )
    status = str(decision["availability_status"])
    reason = decision["availability_reason"]
    available_time = decision["available_time"]
    alternative_times = list(decision["alternative_times"])

    return {
        **decision,
        "availability_message_hint": build_availability_message_hint(
            department=str(department),
            date=str(date),
            time=str(time),
            status=status,
            reason=str(reason) if reason is not None else None,
            available_time=str(available_time) if available_time is not None else None,
            alternative_times=[str(item) for item in alternative_times],
        ),
    }


def build_availability_message_hint(
    department: str,
    date: str,
    time: str,
    status: str,
    reason: str | None,
    available_time: str | None,
    alternative_times: list[str],
) -> str:
    if status == "available":
        safe_time = available_time or time
        return f"{date} {safe_time}에 {department} 진료 예약이 가능합니다."

    if reason == "requested_time_full":
        alternatives = format_alternative_times(alternative_times)
        return (
            f"{date} {time}에는 예약이 모두 차 있습니다. 대신 {alternatives} 시간대는 가능합니다."
        )

    if reason == "doctor_unavailable":
        alternatives = format_alternative_times(alternative_times)
        return (
            f"{date} {time}에는 담당 의사 진료가 없습니다. 대신 {alternatives} 예약이 가능합니다."
        )

    if reason == "hospital_closed":
        alternatives = format_alternative_times(alternative_times)
        return f"{date}에는 병원 휴무로 예약이 어렵습니다. 대신 {alternatives} 예약이 가능합니다."

    alternatives = format_alternative_times(alternative_times)
    return f"{date} {time}에는 예약이 어렵습니다. 대신 {alternatives} 예약이 가능합니다."


def format_alternative_times(alternative_times: list[str]) -> str:
    if not alternative_times:
        return "다른 시간대"

    if len(alternative_times) == 1:
        return alternative_times[0]

    return " 또는 ".join(alternative_times)
