from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from services.flow.professor.appointment.state import ProfessorAppointmentState
from services.flow.professor.appointment.nodes import (
    attach_professor_appointment_recommended_replies_node,
    decide_professor_appointment_state_node,
    extract_professor_appointment_info_node,
    generate_professor_appointment_response_node,
)


def build_professor_appointment_graph():
    builder = StateGraph(ProfessorAppointmentState)

    builder.add_node("extract_info", extract_professor_appointment_info_node)
    builder.add_node("decide_state", decide_professor_appointment_state_node)
    builder.add_node("generate_response", generate_professor_appointment_response_node)
    builder.add_node("attach_replies", attach_professor_appointment_recommended_replies_node)

    builder.add_edge(START, "extract_info")
    builder.add_edge("extract_info", "decide_state")
    builder.add_edge("decide_state", "generate_response")
    builder.add_edge("generate_response", "attach_replies")
    builder.add_edge("attach_replies", END)

    return builder.compile()


professor_appointment_graph = build_professor_appointment_graph()
