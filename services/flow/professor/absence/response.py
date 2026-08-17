from __future__ import annotations

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.professor.absence.graph import professor_absence_graph
from services.flow.professor.absence.policy import compact_professor_absence_state
from services.flow.common.scenario_keys import scenario_matches
from services.flow.common.state_contract import DetailedGraphContract, complete_detailed_graph


PROFESSOR_ABSENCE_CONTRACT = DetailedGraphContract(
    category="교수님",
    title="결석 사유 전달",
    graph=professor_absence_graph,
    compact_state=compact_professor_absence_state,
    defaults={"professor_name": "교수님"},
    allowed_conversation_states=frozenset(
        {
            "greeting",
            "collecting_absence_info",
            "confirming_absence_info",
            "absence_noted",
            "closing",
            "END",
        }
    ),
)


def is_professor_absence_request(req: ChatRequest) -> bool:
    """
    교수님 / 결석 사유 전달 시나리오인지 판단한다.
    """
    return scenario_matches(
        req.category,
        req.title,
        expected_category="교수님",
        expected_title="결석 사유 전달",
    )


def complete_professor_absence_with_graph(req: ChatRequest) -> ChatResponse:
    return complete_detailed_graph(req, PROFESSOR_ABSENCE_CONTRACT)
