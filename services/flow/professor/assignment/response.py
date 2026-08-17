from __future__ import annotations

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.professor.assignment.graph import professor_assignment_graph
from services.flow.professor.assignment.llm_structured import (
    PROFESSOR_ASSIGNMENT_USER_ACTIONS,
)
from services.flow.professor.assignment.policy import compact_professor_assignment_state
from services.flow.common.scenario_keys import scenario_matches
from services.flow.common.state_contract import DetailedGraphContract, complete_detailed_graph
from services.flow.common.detailed_state_validation import ProfessorStateContract


PROFESSOR_ASSIGNMENT_STATE_CONTRACT = ProfessorStateContract(
    intent="assignment_inquiry",
    required_fields=("course_name", "assignment_topic", "question", "user_name"),
    allowed_actions=PROFESSOR_ASSIGNMENT_USER_ACTIONS,
    information_complete_states=frozenset({"answering_assignment_question"}),
)


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
    validate_state=PROFESSOR_ASSIGNMENT_STATE_CONTRACT.validate,
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
