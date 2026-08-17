from __future__ import annotations

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.professor.assignment.graph import professor_assignment_graph
from services.flow.professor.assignment.policy import compact_professor_assignment_state
from services.flow.common.scenario_keys import scenario_matches
from services.flow.common.state_contract import DetailedGraphContract, complete_detailed_graph


PROFESSOR_ASSIGNMENT_CONTRACT = DetailedGraphContract(
    category="교수님",
    title="과제 문의",
    graph=professor_assignment_graph,
    compact_state=compact_professor_assignment_state,
    defaults={"professor_name": "교수님"},
    allowed_conversation_states=frozenset(
        {
            "greeting",
            "collecting_assignment_info",
            "answering_assignment_question",
            "closing",
            "END",
        }
    ),
)


def is_professor_assignment_request(req: ChatRequest) -> bool:
    """
    교수님 / 과제 문의 시나리오인지 판단한다.
    """
    return scenario_matches(
        req.category,
        req.title,
        expected_category="교수님",
        expected_title="과제 문의",
    )


def complete_professor_assignment_with_graph(req: ChatRequest) -> ChatResponse:
    return complete_detailed_graph(req, PROFESSOR_ASSIGNMENT_CONTRACT)
