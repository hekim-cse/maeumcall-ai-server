from __future__ import annotations

from services.flow.professor.appointment.nodes import (
    attach_professor_appointment_recommended_replies_node,
    decide_professor_appointment_state_node,
    extract_professor_appointment_info_node,
    generate_professor_appointment_response_node,
)
from services.flow.professor.appointment.state import ProfessorAppointmentState
from services.flow.professor.common.graph import build_professor_graph


def build_professor_appointment_graph():
    return build_professor_graph(
        ProfessorAppointmentState,
        "professor_appointment",
        extract_info=extract_professor_appointment_info_node,
        decide_state=decide_professor_appointment_state_node,
        generate_response=generate_professor_appointment_response_node,
        attach_replies=attach_professor_appointment_recommended_replies_node,
    )


professor_appointment_graph = build_professor_appointment_graph()
