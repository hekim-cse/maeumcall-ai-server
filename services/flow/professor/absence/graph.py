from __future__ import annotations

from services.flow.professor.absence.nodes import (
    attach_professor_absence_recommended_replies_node,
    decide_professor_absence_state_node,
    extract_professor_absence_info_node,
    generate_professor_absence_response_node,
)
from services.flow.professor.absence.state import ProfessorAbsenceState
from services.flow.professor.common.graph import build_professor_graph


def build_professor_absence_graph():
    return build_professor_graph(
        ProfessorAbsenceState,
        "professor_absence",
        extract_info=extract_professor_absence_info_node,
        decide_state=decide_professor_absence_state_node,
        generate_response=generate_professor_absence_response_node,
        attach_replies=attach_professor_absence_recommended_replies_node,
    )


professor_absence_graph = build_professor_absence_graph()
