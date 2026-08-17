from __future__ import annotations

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.reservation.hair_salon.graph import hair_salon_reservation_graph
from services.flow.common.scenario_keys import scenario_matches
from services.flow.common.state_contract import DetailedGraphContract, complete_detailed_graph
from services.flow.reservation.hair_salon.policy import compact_hair_salon_state


_CONTRACT = DetailedGraphContract(
    category="예약",
    title="미용실 예약",
    graph=hair_salon_reservation_graph,
    compact_state=compact_hair_salon_state,
    defaults={"service_name": "마음헤어"},
    allowed_conversation_states=frozenset(
        {
            "greeting",
            "collecting_reservation_info",
            "confirming_info",
            "checking_availability",
            "reservation_available",
            "reservation_unavailable",
            "reservation_confirmed",
            "closing",
            "END",
        }
    ),
)


def is_hair_salon_reservation_request(req: ChatRequest) -> bool:
    """
    미용실 예약 LangGraph 라우팅 여부를 판단한다.

    등록된 category/title 키를 사용해
    category/title의 명시적인 시나리오 매핑만 사용한다.
    """
    return scenario_matches(
        getattr(req, "category", ""),
        getattr(req, "title", ""),
        expected_category="예약",
        expected_title="미용실 예약",
    )


def complete_hair_salon_reservation_with_graph(req: ChatRequest) -> ChatResponse:
    return complete_detailed_graph(req, _CONTRACT)
