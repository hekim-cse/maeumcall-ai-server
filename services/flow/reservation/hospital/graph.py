from __future__ import annotations

from langgraph.graph import StateGraph, START, END
from services.flow.reservation.hospital.state import HospitalReservationState
from services.flow.reservation.hospital.policy import route_after_decide
from services.flow.reservation.hospital.response_policy import build_hospital_response
from services.flow.reservation.hospital.nodes import (
    attach_recommended_replies_node,
    check_availability_node,
    decide_next_state_node,
    extract_info_node,
    parse_user_action_node,
)

from services.flow.reservation.hospital.generation import generate_ai_message_node

__all__ = [
    "build_hospital_reservation_graph",
    "build_hospital_response",
    "hospital_reservation_graph",
]


def build_hospital_reservation_graph():
    builder = StateGraph(HospitalReservationState)

    builder.add_node("extract_info", extract_info_node)
    builder.add_node("parse_user_action", parse_user_action_node)
    builder.add_node("decide_next_state", decide_next_state_node)
    builder.add_node("check_availability", check_availability_node)
    builder.add_node("generate_ai_message", generate_ai_message_node)
    builder.add_node("attach_recommended_replies", attach_recommended_replies_node)

    builder.add_edge(START, "extract_info")
    builder.add_edge("extract_info", "parse_user_action")
    builder.add_edge("parse_user_action", "decide_next_state")

    builder.add_conditional_edges(
        "decide_next_state",
        route_after_decide,
        {
            "check_availability": "check_availability",
            "generate_ai_message": "generate_ai_message",
        },
    )

    builder.add_edge("check_availability", "generate_ai_message")
    builder.add_edge("generate_ai_message", "attach_recommended_replies")
    builder.add_edge("attach_recommended_replies", END)

    return builder.compile()

hospital_reservation_graph = build_hospital_reservation_graph()
