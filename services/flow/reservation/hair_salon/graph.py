from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from core.observability import add_observed_node
from services.flow.reservation.hair_salon.nodes import (
    attach_hair_salon_recommended_replies_node,
    check_hair_salon_availability_node,
    decide_hair_salon_state_node,
    extract_hair_salon_info_node,
    generate_hair_salon_response_node,
)
from services.flow.reservation.hair_salon.state import HairSalonReservationState


def route_after_hair_salon_decide(state: HairSalonReservationState) -> str:
    """
    상태 결정 후 다음 노드를 선택한다.
    """
    if state.get("conversation_state") == "checking_availability":
        return "check_availability"

    return "generate_response"


def build_hair_salon_reservation_graph():
    builder = StateGraph(HairSalonReservationState)

    graph_name = "hair_salon_reservation"
    add_observed_node(builder, graph_name, "extract_info", extract_hair_salon_info_node)
    add_observed_node(builder, graph_name, "decide_state", decide_hair_salon_state_node)
    add_observed_node(builder, graph_name, "check_availability", check_hair_salon_availability_node)
    add_observed_node(builder, graph_name, "generate_response", generate_hair_salon_response_node)
    add_observed_node(
        builder,
        graph_name,
        "attach_replies",
        attach_hair_salon_recommended_replies_node,
    )

    builder.add_edge(START, "extract_info")
    builder.add_edge("extract_info", "decide_state")
    builder.add_conditional_edges(
        "decide_state",
        route_after_hair_salon_decide,
        {
            "check_availability": "check_availability",
            "generate_response": "generate_response",
        },
    )
    builder.add_edge("check_availability", "generate_response")
    builder.add_edge("generate_response", "attach_replies")
    builder.add_edge("attach_replies", END)

    return builder.compile()


hair_salon_reservation_graph = build_hair_salon_reservation_graph()
