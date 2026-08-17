from __future__ import annotations

from services.flow.reservation.hair_salon.policy import (
    get_missing_hair_salon_fields,
)

HAIR_SALON_FIELD_LABELS = {
    "date": "날짜",
    "time": "시간",
    "service_type": "시술 종류",
    "designer": "디자이너",
    "user_name": "예약자 성함",
}


def build_hair_salon_response(conversation_state: str, state: dict) -> str:
    date = state.get("date") or "원하시는 날짜"
    time = state.get("time") or "원하시는 시간"
    service_type = state.get("service_type") or "원하시는 시술"
    designer = state.get("designer") or "원하시는 디자이너"
    user_name = state.get("user_name") or "예약자"

    if conversation_state == "collecting_reservation_info":
        missing = get_missing_hair_salon_fields(state)
        if missing == ["user_name"]:
            return "예약자 성함을 말씀해주시겠어요?"
        if missing == ["designer"]:
            return "원하시는 디자이너가 있으신가요? 없으시면 가능한 디자이너로 도와드리겠습니다."
        if not missing:
            raise ValueError("collecting_reservation_info requires at least one missing field")
        fields = ", ".join(HAIR_SALON_FIELD_LABELS[field] for field in missing)
        return f"예약 도와드리겠습니다. 다음 정보를 편하게 말씀해주시겠어요? {fields}."
    if conversation_state == "confirming_info":
        return (
            f"{date} {time}에 {designer} 선생님으로 {service_type} 예약을 원하시는 것이 맞으실까요?"
        )
    if conversation_state == "checking_availability":
        return "잠시만요. 예약 가능한지 확인해보겠습니다."
    if conversation_state == "reservation_available":
        available_time = state.get("available_time") or state.get("selected_time") or time
        return f"{date} {available_time}에 {designer} 선생님으로 {service_type} 예약 가능합니다. 이 시간 괜찮으세요?"
    if conversation_state == "reservation_unavailable":
        alternatives = state.get("alternative_times") or []
        if alternatives:
            return f"죄송하지만 요청하신 시간은 예약이 어렵습니다. 대신 {' 또는 '.join(alternatives)}는 가능합니다. 괜찮으신 시간이 있으세요?"
        return "죄송하지만 요청하신 시간은 예약이 어렵습니다. 다른 시간대로 확인해드릴까요?"
    if conversation_state == "reservation_confirmed":
        final_time = state.get("selected_time") or state.get("available_time") or time
        return f"{user_name}님, {date} {final_time}에 {designer} 선생님 {service_type} 예약 완료됐습니다."
    if conversation_state == "closing":
        return "네, 감사합니다. 방문 때 뵙겠습니다."
    if conversation_state == "END":
        return "감사합니다. 좋은 하루 보내세요."
    raise ValueError(f"unsupported hair salon conversation state: {conversation_state}")
