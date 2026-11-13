from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from core.observability import add_observed_node


def build_professor_graph(
    state_type,
    graph_name: str,
    *,
    extract_info,
    decide_state,
    generate_response,
    attach_replies,
):
    """Compile the shared four-step professor conversation topology."""
    builder = StateGraph(state_type)

    add_observed_node(builder, graph_name, "extract_info", extract_info)
    add_observed_node(builder, graph_name, "decide_state", decide_state)
    add_observed_node(builder, graph_name, "generate_response", generate_response)
    add_observed_node(builder, graph_name, "attach_replies", attach_replies)

    builder.add_edge(START, "extract_info")
    builder.add_edge("extract_info", "decide_state")
    builder.add_edge("decide_state", "generate_response")
    builder.add_edge("generate_response", "attach_replies")
    builder.add_edge("attach_replies", END)

    return builder.compile()
