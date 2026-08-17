from __future__ import annotations

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.reservation.hair_salon.graph import hair_salon_reservation_graph
from services.flow.reservation.hair_salon.llm_structured import HAIR_SALON_USER_ACTIONS
from services.flow.common.scenario_keys import scenario_matches
from services.flow.common.state_contract import DetailedGraphContract, complete_detailed_graph
from services.flow.common.detailed_state_validation import ReservationStateContract
from services.flow.reservation.hair_salon.policy import compact_hair_salon_state


HAIR_SALON_STATE_CONTRACT = ReservationStateContract(
    identity_field="service_name",
    required_fields=("date", "time", "service_type", "designer", "user_name"),
    allowed_actions=HAIR_SALON_USER_ACTIONS | {"invalid_alternative_time"},
    information_complete_states=frozenset(
        {
            "confirming_info",
            "checking_availability",
            "reservation_available",
            "reservation_unavailable",
            "reservation_confirmed",
        }
    ),
)


HAIR_SALON_RESERVATION_CONTRACT = DetailedGraphContract(
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
    validate_state=HAIR_SALON_STATE_CONTRACT.validate,
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
    return complete_detailed_graph(req, HAIR_SALON_RESERVATION_CONTRACT)
