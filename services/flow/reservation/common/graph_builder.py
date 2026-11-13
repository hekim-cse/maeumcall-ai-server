from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from langgraph.graph import END, START, StateGraph

from core.observability import add_observed_node


def route_after_availability_decide(state: Mapping[str, object]) -> str:
    if state.get("conversation_state") == "checking_availability":
        return "check_availability"
    return "generate_response"


def build_availability_reservation_graph(
    *,
    state_type: type,
    graph_name: str,
    extract_info: Callable[..., Any],
    decide_state: Callable[..., Any],
    check_availability: Callable[..., Any],
    generate_response: Callable[..., Any],
    attach_replies: Callable[..., Any],
    route_after_decide: Callable[..., str],
):
    """Assemble the shared five-node topology of availability-based reservations."""
    builder = StateGraph(state_type)
    for node_name, action in (
        ("extract_info", extract_info),
        ("decide_state", decide_state),
        ("check_availability", check_availability),
        ("generate_response", generate_response),
        ("attach_replies", attach_replies),
    ):
        add_observed_node(builder, graph_name, node_name, action)

    builder.add_edge(START, "extract_info")
    builder.add_edge("extract_info", "decide_state")
    builder.add_conditional_edges(
        "decide_state",
        route_after_decide,
        {
            "check_availability": "check_availability",
            "generate_response": "generate_response",
        },
    )
    builder.add_edge("check_availability", "generate_response")
    builder.add_edge("generate_response", "attach_replies")
    builder.add_edge("attach_replies", END)
    return builder.compile()
