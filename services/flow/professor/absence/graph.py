from __future__ import annotations

from langgraph.graph import StateGraph, START, END
from core.observability import add_observed_node

from services.flow.professor.absence.state import ProfessorAbsenceState
from services.flow.professor.absence.nodes import (
    attach_professor_absence_recommended_replies_node,
    decide_professor_absence_state_node,
    extract_professor_absence_info_node,
    generate_professor_absence_response_node,
)


def build_professor_absence_graph():
    builder = StateGraph(ProfessorAbsenceState)

    graph_name = "professor_absence"
    add_observed_node(builder, graph_name, "extract_info", extract_professor_absence_info_node)
    add_observed_node(builder, graph_name, "decide_state", decide_professor_absence_state_node)
    add_observed_node(
        builder,
        graph_name,
        "generate_response",
        generate_professor_absence_response_node,
    )
    add_observed_node(
        builder,
        graph_name,
        "attach_replies",
        attach_professor_absence_recommended_replies_node,
    )

    builder.add_edge(START, "extract_info")
    builder.add_edge("extract_info", "decide_state")
    builder.add_edge("decide_state", "generate_response")
    builder.add_edge("generate_response", "attach_replies")
    builder.add_edge("attach_replies", END)

    return builder.compile()


professor_absence_graph = build_professor_absence_graph()
