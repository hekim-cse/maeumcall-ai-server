from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from services.flow.reservation.hair_salon.state import HairSalonReservationState
from services.flow.reservation.hair_salon.nodes import (
    attach_hair_salon_recommended_replies_node,
    decide_hair_salon_state_node,
    extract_hair_salon_info_node,
    generate_hair_salon_response_node,
)


def build_hair_salon_reservation_graph():
    builder = StateGraph(HairSalonReservationState)

    builder.add_node("extract_info", extract_hair_salon_info_node)
    builder.add_node("decide_state", decide_hair_salon_state_node)
    builder.add_node("generate_response", generate_hair_salon_response_node)
    builder.add_node("attach_replies", attach_hair_salon_recommended_replies_node)

    builder.add_edge(START, "extract_info")
    builder.add_edge("extract_info", "decide_state")
    builder.add_edge("decide_state", "generate_response")
    builder.add_edge("generate_response", "attach_replies")
    builder.add_edge("attach_replies", END)

    return builder.compile()


hair_salon_reservation_graph = build_hair_salon_reservation_graph()
