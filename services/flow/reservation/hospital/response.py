# LangGraph 실행 결과를 ChatResponse로 바꾸는 파일

from __future__ import annotations

from typing import Dict, Any

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.reservation.hospital.graph import hospital_reservation_graph
from services.flow.common.scenario_keys import scenario_matches
from services.flow.common.state_contract import DetailedGraphContract, complete_detailed_graph


def is_hospital_reservation_request(req: ChatRequest) -> bool:
    """
    병원 예약 LangGraph 라우팅 여부를 판단한다.

    등록된 category/title 키를 사용해
    category/title의 명시적인 시나리오 매핑만 사용한다.

    이유:
    - "예약"이라는 단어만으로 병원 예약 graph에 보내면
      식당 예약, 스터디룸 예약, 미용실 예약도 병원 graph로 잘못 들어갈 수 있다.
    - LangGraph case는 시나리오 단위로 명확하게 분리되어야 한다.
    """
    return scenario_matches(
        getattr(req, "category", ""),
        getattr(req, "title", ""),
        expected_category="예약",
        expected_title="병원 예약",
    )


def compact_hospital_state(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "intent": result.get("intent"),
        "service_name": result.get("service_name"),
        "department": result.get("department"),
        "date": result.get("date"),
        "time": result.get("time"),
        "conversation_state": result.get("conversation_state"),
        "last_ai_message": result.get("ai_message"),

        "user_action": result.get("user_action"),
        "selected_time": result.get("selected_time"),
        
        "availability_status": result.get("availability_status"),
        "availability_reason": result.get("availability_reason"),
        "available_time": result.get("available_time"),
        "alternative_times": result.get("alternative_times") or [],
        "availability_message_hint": result.get("availability_message_hint"),
        "reservation_confirmed": result.get("reservation_confirmed"),
    }


_CONTRACT = DetailedGraphContract(
    category="예약",
    title="병원 예약",
    graph=hospital_reservation_graph,
    compact_state=compact_hospital_state,
    defaults={"service_name": "마음병원"},
    allowed_conversation_states=frozenset(
        {
            "greeting",
            "asking_purpose",
            "asking_department",
            "asking_date",
            "asking_time",
            "confirming_info",
            "checking_availability",
            "reservation_lookup",
            "reservation_available",
            "reservation_unavailable",
            "suggest_alternative",
            "reservation_confirmed",
            "closing",
            "END",
        }
    ),
)


def complete_hospital_reservation_with_graph(req: ChatRequest) -> ChatResponse:
    return complete_detailed_graph(req, _CONTRACT)
