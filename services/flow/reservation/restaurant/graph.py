from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from services.flow.reservation.restaurant.state import RestaurantReservationState
from services.flow.reservation.restaurant.nodes import (
    attach_restaurant_recommended_replies_node,
    decide_restaurant_state_node,
    extract_restaurant_info_node,
    generate_restaurant_response_node,
)


def build_restaurant_reservation_graph():
    builder = StateGraph(RestaurantReservationState)

    builder.add_node("extract_info", extract_restaurant_info_node)
    builder.add_node("decide_state", decide_restaurant_state_node)
    builder.add_node("generate_response", generate_restaurant_response_node)
    builder.add_node("attach_replies", attach_restaurant_recommended_replies_node)

    builder.add_edge(START, "extract_info")
    builder.add_edge("extract_info", "decide_state")
    builder.add_edge("decide_state", "generate_response")
    builder.add_edge("generate_response", "attach_replies")
    builder.add_edge("attach_replies", END)

    return builder.compile()


restaurant_reservation_graph = build_restaurant_reservation_graph()
