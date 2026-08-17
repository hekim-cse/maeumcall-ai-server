from __future__ import annotations

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.common.detailed_state_validation import ReservationStateContract
from services.flow.common.scenario_keys import scenario_matches
from services.flow.common.state_contract import DetailedGraphContract, complete_detailed_graph
from services.flow.reservation.restaurant.graph import restaurant_reservation_graph
from services.flow.reservation.restaurant.llm_structured import RESTAURANT_USER_ACTIONS
from services.flow.reservation.restaurant.policy import compact_restaurant_state

RESTAURANT_STATE_CONTRACT = ReservationStateContract(
    identity_field="service_name",
    required_fields=("date", "time", "party_size", "user_name"),
    allowed_actions=RESTAURANT_USER_ACTIONS,
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


RESTAURANT_RESERVATION_CONTRACT = DetailedGraphContract(
    category="예약",
    title="식당 예약",
    graph=restaurant_reservation_graph,
    compact_state=compact_restaurant_state,
    defaults={"service_name": "마음식당"},
    allowed_conversation_states=frozenset(
        {
            "greeting",
            "collecting_reservation_info",
            "asking_date",
            "asking_time",
            "asking_party_size",
            "confirming_info",
            "checking_availability",
            "reservation_available",
            "reservation_unavailable",
            "reservation_confirmed",
            "closing",
            "END",
        }
    ),
    validate_state=RESTAURANT_STATE_CONTRACT.validate,
)


def is_restaurant_reservation_request(req: ChatRequest) -> bool:
    """
    식당 예약 LangGraph 라우팅 여부를 판단한다.

    등록된 category/title 키를 사용해
    category/title의 명시적인 시나리오 매핑만 사용한다.
    """
    return scenario_matches(
        getattr(req, "category", ""),
        getattr(req, "title", ""),
        expected_category="예약",
        expected_title="식당 예약",
    )


def complete_restaurant_reservation_with_graph(req: ChatRequest) -> ChatResponse:
    return complete_detailed_graph(req, RESTAURANT_RESERVATION_CONTRACT)
