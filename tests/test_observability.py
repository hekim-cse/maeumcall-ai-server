from __future__ import annotations

import pytest
from typing_extensions import TypedDict

from fastapi.testclient import TestClient
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
from prometheus_client import REGISTRY

from core.observability import observe_graph_node
from main import app
from schemas.chat_models import ChatRequest
from services.flow.common.state_contract import ScenarioStateContractError
from services.flow.scenario import graph as graph_module
from services.flow.scenario.response import complete_scenario_graph_if_supported
from services.flow.reservation.hospital.llm_structured import (
    analyze_hospital_reservation_user_message,
)


pytestmark = pytest.mark.unit


def _sample(name: str, labels: dict[str, str]) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_langgraph_node_attempt_and_duration_are_recorded(monkeypatch):
    labels = {
        "graph": "registered_scenario",
        "node": "prepare_turn",
        "outcome": "success",
    }
    attempts_before = _sample(
        "maeumcall_langgraph_node_attempts_total",
        labels,
    )
    observations_before = _sample(
        "maeumcall_langgraph_node_duration_seconds_count",
        labels,
    )
    monkeypatch.setattr(
        graph_module,
        "complete_json_messages",
        lambda messages: (
            '{"action":"continue","response":"계속 말씀해 주세요.",'
            '"etiquette_tip":null}'
        ),
    )

    response = complete_scenario_graph_if_supported(
        ChatRequest(
            category="친구",
            title="심심해서 거는 전화",
            description="통화 연습",
            userMessage="안녕",
        )
    )

    assert response is not None
    assert _sample("maeumcall_langgraph_node_attempts_total", labels) == (
        attempts_before + 1
    )
    assert _sample("maeumcall_langgraph_node_duration_seconds_count", labels) == (
        observations_before + 1
    )


def test_structured_output_retry_and_contract_failure_are_recorded(monkeypatch):
    responses = iter(
        [
            "JSON 형식이 아닌 응답",
            (
                '{"intent":"reservation","department":"내과",'
                '"date":"내일","time":"오후 3시",'
                '"user_name":"김개굴",'
                '"user_action":"continue_collecting","selected_time":null}'
            ),
        ]
    )
    monkeypatch.setattr(
        "services.flow.reservation.hospital.llm_structured.complete_hf_json",
        lambda messages: next(responses),
    )
    retry_labels = {
        "operation": "hospital_extraction",
        "reason": "JSONDecodeError",
    }
    failure_labels = {
        "contract": "structured_output",
        "code": "JSONDecodeError",
    }
    retries_before = _sample(
        "maeumcall_structured_output_retries_total",
        retry_labels,
    )
    failures_before = _sample(
        "maeumcall_contract_failures_total",
        failure_labels,
    )

    result = analyze_hospital_reservation_user_message("greeting", "예약할게요.")

    assert result["department"] == "내과"
    assert _sample("maeumcall_structured_output_retries_total", retry_labels) == (
        retries_before + 1
    )
    assert _sample("maeumcall_contract_failures_total", failure_labels) == (
        failures_before + 1
    )


def test_scenario_state_contract_failure_is_recorded():
    labels = {
        "contract": "scenario_state",
        "code": "SCENARIO_STATE_MISMATCH",
    }
    before = _sample("maeumcall_contract_failures_total", labels)

    ScenarioStateContractError(
        "SCENARIO_STATE_MISMATCH",
        "현재 시나리오와 전달된 상태가 일치하지 않습니다.",
    )

    assert _sample("maeumcall_contract_failures_total", labels) == before + 1


def test_langgraph_retry_attempt_is_recorded():
    class RetryState(TypedDict):
        value: int

    calls = 0

    def retryable_node(state: RetryState) -> RetryState:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("provider connection interrupted")
        return {"value": state["value"] + 1}

    builder = StateGraph(RetryState)
    builder.add_node(
        "provider_call",
        observe_graph_node("retry_policy_contract", "provider_call", retryable_node),
        retry_policy=RetryPolicy(
            max_attempts=2,
            initial_interval=0,
            backoff_factor=1,
            max_interval=0,
            jitter=False,
            retry_on=ConnectionError,
        ),
    )
    builder.add_edge(START, "provider_call")
    builder.add_edge("provider_call", END)
    graph = builder.compile()
    retry_labels = {
        "graph": "retry_policy_contract",
        "node": "provider_call",
    }
    retries_before = _sample(
        "maeumcall_langgraph_node_retries_total",
        retry_labels,
    )

    result = graph.invoke({"value": 1})

    assert result["value"] == 2
    assert calls == 2
    assert _sample("maeumcall_langgraph_node_retries_total", retry_labels) == (
        retries_before + 1
    )


def test_metrics_endpoint_uses_prometheus_text_format_without_identity_labels():
    response = TestClient(app).get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "maeumcall_langgraph_node_duration_seconds" in response.text
    assert "maeumcall_contract_failures_total" in response.text
    assert "user_id=" not in response.text
    assert "request_id=" not in response.text
