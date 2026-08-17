from __future__ import annotations

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.professor.appointment.graph import professor_appointment_graph
from services.flow.professor.appointment.policy import compact_professor_appointment_state
from services.flow.common.scenario_keys import scenario_matches
from services.flow.common.state_contract import DetailedGraphContract, complete_detailed_graph


_CONTRACT = DetailedGraphContract(
    category="교수님",
    title="면담 예약",
    graph=professor_appointment_graph,
    compact_state=compact_professor_appointment_state,
    defaults={"professor_name": "교수님"},
    allowed_conversation_states=frozenset(
        {
            "greeting",
            "collecting_appointment_info",
            "confirming_info",
            "appointment_confirmed",
            "closing",
            "END",
        }
    ),
)


def is_professor_appointment_request(req: ChatRequest) -> bool:
    """
    교수님 / 면담 예약 시나리오인지 확인한다.
    """
    return scenario_matches(
        req.category,
        req.title,
        expected_category="교수님",
        expected_title="면담 예약",
    )


def complete_professor_appointment_with_graph(req: ChatRequest) -> ChatResponse:
    return complete_detailed_graph(req, _CONTRACT)
