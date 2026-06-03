from __future__ import annotations

from typing import Dict, Any

from services.flow.reservation.hospital.state import HospitalReservationState


def clear_reservation_lookup_fields() -> Dict[str, Any]:
    """
    날짜/시간/진료과 변경처럼 예약 조건이 바뀌는 경우,
    이전 예약 가능 여부 조회 결과를 초기화한다.

    예:
    - 이전 상태: reservation_unavailable
    - 이전 대안 시간: 오후 4시, 오후 5시
    - 사용자: 다른 날짜로 확인해주세요.

    이때 이전 날짜의 조회 결과가 새 날짜 흐름에 남지 않도록 비운다.
    """
    return {
        "availability_status": None,
        "availability_reason": None,
        "available_time": None,
        "alternative_times": [],
        "availability_message_hint": None,
        "reservation_confirmed": None,
        "selected_time": None,
        "simulation_result": None,
    }


def should_use_template_first(conversation_state: str) -> bool:
    """
    LLM 호출 없이 정형 응답으로 충분한 상태인지 판단한다.

    이 상태들은 응답 문장이 거의 고정되어 있어
    Kanana 호출보다 fallback/template 응답을 우선 사용하는 것이 안정적이다.
    """
    return conversation_state in {
        "asking_department",
        "asking_date",
        "asking_time",
        "confirming_info",
        "checking_availability",
        "reservation_available",
        "reservation_confirmed",
        "closing",
        "END",
    }


def route_after_decide(state: HospitalReservationState) -> str:
    conversation_state = state.get("conversation_state")

    if conversation_state == "reservation_lookup":
        return "check_availability"

    return "generate_ai_message"
