from __future__ import annotations

import os
from collections.abc import Callable
from time import perf_counter
from typing import Any

from langgraph.runtime import Runtime
from prometheus_client import (
    REGISTRY,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
)

LANGGRAPH_NODE_ATTEMPTS = Counter(
    "maeumcall_langgraph_node_attempts_total",
    "LangGraph node attempts grouped by graph, node, and outcome.",
    ("graph", "node", "outcome"),
)
LANGGRAPH_NODE_RETRIES = Counter(
    "maeumcall_langgraph_node_retries_total",
    "LangGraph node attempts whose one-based attempt number is greater than one.",
    ("graph", "node"),
)
LANGGRAPH_NODE_DURATION = Histogram(
    "maeumcall_langgraph_node_duration_seconds",
    "LangGraph node execution duration in seconds.",
    ("graph", "node", "outcome"),
    buckets=(
        0.001,
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1,
        2.5,
        5,
        10,
        30,
    ),
)
STRUCTURED_OUTPUT_RETRIES = Counter(
    "maeumcall_structured_output_retries_total",
    "Structured model outputs regenerated after a contract validation failure.",
    ("operation", "reason"),
)
CONTRACT_FAILURES = Counter(
    "maeumcall_contract_failures_total",
    "Application contract failures grouped by bounded contract and code values.",
    ("contract", "code"),
)
TTS_SYNTHESIS_ATTEMPTS = Counter(
    "maeumcall_tts_synthesis_attempts_total",
    "TTS synthesis attempts grouped by provider, model state, and outcome.",
    ("provider", "model_state", "outcome"),
)
TTS_SYNTHESIS_DURATION = Histogram(
    "maeumcall_tts_synthesis_duration_seconds",
    "TTS runtime phase duration in seconds.",
    ("provider", "phase", "model_state", "outcome"),
    buckets=(
        0.001,
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1,
        2.5,
        5,
        10,
        30,
        60,
        120,
    ),
)


def observe_graph_node(
    graph_name: str,
    node_name: str,
    action: Callable[[Any], Any],
) -> Callable[[Any, Runtime], Any]:
    """Wrap one synchronous LangGraph node without adding fallback behavior."""

    def observed(state: Any, runtime: Runtime) -> Any:
        started_at = perf_counter()
        outcome = "success"
        attempt = runtime.execution_info.node_attempt
        if attempt > 1:
            LANGGRAPH_NODE_RETRIES.labels(graph=graph_name, node=node_name).inc()
        try:
            return action(state)
        except Exception:
            outcome = "error"
            raise
        finally:
            LANGGRAPH_NODE_ATTEMPTS.labels(
                graph=graph_name,
                node=node_name,
                outcome=outcome,
            ).inc()
            LANGGRAPH_NODE_DURATION.labels(
                graph=graph_name,
                node=node_name,
                outcome=outcome,
            ).observe(perf_counter() - started_at)

    observed.__name__ = f"observed_{graph_name}_{node_name}"
    return observed


def add_observed_node(
    builder: Any,
    graph_name: str,
    node_name: str,
    action: Callable[[Any], Any],
) -> None:
    builder.add_node(
        node_name,
        observe_graph_node(graph_name, node_name, action),
    )


def record_structured_output_retry(operation: str, reason: str) -> None:
    STRUCTURED_OUTPUT_RETRIES.labels(operation=operation, reason=reason).inc()


def record_contract_failure(contract: str, code: str) -> None:
    CONTRACT_FAILURES.labels(contract=contract, code=code).inc()


def record_tts_synthesis(
    *,
    provider: str,
    model_state: str,
    outcome: str,
    phase_durations: dict[str, float],
) -> None:
    """Record bounded TTS runtime labels without text or user identifiers."""

    TTS_SYNTHESIS_ATTEMPTS.labels(
        provider=provider,
        model_state=model_state,
        outcome=outcome,
    ).inc()
    for phase, duration in phase_durations.items():
        TTS_SYNTHESIS_DURATION.labels(
            provider=provider,
            phase=phase,
            model_state=model_state,
            outcome=outcome,
        ).observe(max(duration, 0.0))


def render_metrics() -> bytes:
    """Render the process registry or aggregate an externally configured worker set."""
    if os.getenv("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry(support_collectors_without_names=True)
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry)
    return generate_latest(REGISTRY)
