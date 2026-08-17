from __future__ import annotations

from langgraph.graph import StateGraph, START, END
from core.observability import add_observed_node

from services.flow.professor.assignment.state import ProfessorAssignmentState
from services.flow.professor.assignment.nodes import (
    attach_professor_assignment_recommended_replies_node,
    decide_professor_assignment_state_node,
    extract_professor_assignment_info_node,
    generate_professor_assignment_response_node,
)


def build_professor_assignment_graph():
    builder = StateGraph(ProfessorAssignmentState)

    graph_name = "professor_assignment"
    add_observed_node(
        builder, graph_name, "extract_info", extract_professor_assignment_info_node
    )
    add_observed_node(
        builder, graph_name, "decide_state", decide_professor_assignment_state_node
    )
    add_observed_node(
        builder,
        graph_name,
        "generate_response",
        generate_professor_assignment_response_node,
    )
    add_observed_node(
        builder,
        graph_name,
        "attach_replies",
        attach_professor_assignment_recommended_replies_node,
    )

    builder.add_edge(START, "extract_info")
    builder.add_edge("extract_info", "decide_state")
    builder.add_edge("decide_state", "generate_response")
    builder.add_edge("generate_response", "attach_replies")
    builder.add_edge("attach_replies", END)

    return builder.compile()


professor_assignment_graph = build_professor_assignment_graph()
