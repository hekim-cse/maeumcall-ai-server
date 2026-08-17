from __future__ import annotations

from langgraph.graph import StateGraph, START, END
from core.observability import add_observed_node

from services.flow.reservation.restaurant.state import RestaurantReservationState
from services.flow.reservation.restaurant.nodes import (
    attach_restaurant_recommended_replies_node,
    check_restaurant_availability_node,
    decide_restaurant_state_node,
    extract_restaurant_info_node,
    generate_restaurant_response_node,
)


def route_after_restaurant_decide(state: RestaurantReservationState) -> str:
    """
    decide_state 이후 다음 노드를 결정한다.
    """
    conversation_state = state.get("conversation_state")

    if conversation_state == "checking_availability":
        return "check_availability"

    return "generate_response"


def build_restaurant_reservation_graph():
    builder = StateGraph(RestaurantReservationState)

    graph_name = "restaurant_reservation"
    add_observed_node(builder, graph_name, "extract_info", extract_restaurant_info_node)
    add_observed_node(builder, graph_name, "decide_state", decide_restaurant_state_node)
    add_observed_node(
        builder, graph_name, "check_availability", check_restaurant_availability_node
    )
    add_observed_node(
        builder, graph_name, "generate_response", generate_restaurant_response_node
    )
    add_observed_node(
        builder,
        graph_name,
        "attach_replies",
        attach_restaurant_recommended_replies_node,
    )

    builder.add_edge(START, "extract_info")
    builder.add_edge("extract_info", "decide_state")

    builder.add_conditional_edges(
        "decide_state",
        route_after_restaurant_decide,
        {
            "check_availability": "check_availability",
            "generate_response": "generate_response",
        },
    )

    builder.add_edge("check_availability", "generate_response")
    builder.add_edge("generate_response", "attach_replies")
    builder.add_edge("attach_replies", END)

    return builder.compile()


restaurant_reservation_graph = build_restaurant_reservation_graph()
