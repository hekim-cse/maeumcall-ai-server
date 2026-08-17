from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from core.observability import add_observed_node
from services.flow.service_workflow.contracts import ServiceWorkflowSpec
from services.flow.service_workflow.nodes import (
    build_decide_node,
    build_extract_node,
    build_replies_node,
    build_response_node,
)
from services.flow.service_workflow.state import ServiceWorkflowState


def build_service_workflow_graph(spec: ServiceWorkflowSpec):
    builder = StateGraph(ServiceWorkflowState)
    add_observed_node(builder, spec.graph_name, "extract_info", build_extract_node(spec))
    add_observed_node(builder, spec.graph_name, "decide_state", build_decide_node(spec))
    add_observed_node(builder, spec.graph_name, "generate_response", build_response_node(spec))
    add_observed_node(builder, spec.graph_name, "attach_replies", build_replies_node(spec))
    builder.add_edge(START, "extract_info")
    builder.add_edge("extract_info", "decide_state")
    builder.add_edge("decide_state", "generate_response")
    builder.add_edge("generate_response", "attach_replies")
    builder.add_edge("attach_replies", END)
    return builder.compile()
