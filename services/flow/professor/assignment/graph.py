from __future__ import annotations

from services.flow.professor.assignment.nodes import (
    attach_professor_assignment_recommended_replies_node,
    decide_professor_assignment_state_node,
    extract_professor_assignment_info_node,
    generate_professor_assignment_response_node,
)
from services.flow.professor.assignment.state import ProfessorAssignmentState
from services.flow.professor.common.graph import build_professor_graph


def build_professor_assignment_graph():
    return build_professor_graph(
        ProfessorAssignmentState,
        "professor_assignment",
        extract_info=extract_professor_assignment_info_node,
        decide_state=decide_professor_assignment_state_node,
        generate_response=generate_professor_assignment_response_node,
        attach_replies=attach_professor_assignment_recommended_replies_node,
    )


professor_assignment_graph = build_professor_assignment_graph()
