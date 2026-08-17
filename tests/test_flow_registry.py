from collections import Counter

import pytest
from fastapi.testclient import TestClient

from main import app
from services.flow import registry as registry_module
from services.flow.registry import (
    FLOW_REGISTRY,
    FlowExecutionMode,
    get_flow_registration,
)
from services.flow.scenario.registry import ScenarioConfig

pytestmark = pytest.mark.unit


def test_all_product_scenarios_have_one_execution_mode():
    counts = Counter(registration.mode for registration in FLOW_REGISTRY.values())

    assert len(FLOW_REGISTRY) == 32
    assert counts == {
        FlowExecutionMode.DETAILED: 16,
        FlowExecutionMode.REGISTERED: 16,
    }


def test_detailed_and_registered_contracts_are_separated():
    for registration in FLOW_REGISTRY.values():
        if registration.mode is FlowExecutionMode.DETAILED:
            assert registration.detailed_contract is not None
            assert registration.category in {"예약", "교수님", "배달", "시청", "고객센터"}
        else:
            assert registration.detailed_contract is None
            assert registration.category in {"가족", "친구", "연인", "회사"}


def test_each_detailed_registration_owns_a_distinct_compiled_graph():
    detailed_graphs = [
        registration.detailed_contract.graph
        for registration in FLOW_REGISTRY.values()
        if registration.mode is FlowExecutionMode.DETAILED
    ]

    assert len(detailed_graphs) == 16
    assert len({id(graph) for graph in detailed_graphs}) == 16


def test_mobile_display_icon_and_spacing_resolve_to_same_registration():
    plain = get_flow_registration("예약", "병원 예약")
    mobile = get_flow_registration(" 예약 ", "🏥 병원 예약")

    assert plain is not None
    assert mobile is plain
    assert mobile.mode is FlowExecutionMode.DETAILED


def test_unknown_scenario_has_no_execution_mode():
    assert get_flow_registration("기타", "등록되지 않은 상황") is None


def test_duplicate_scenario_registration_fails_during_registry_build(monkeypatch):
    contract = registry_module.DETAILED_GRAPH_CONTRACTS[0]
    duplicate = ScenarioConfig(
        category=contract.category,
        title=contract.title,
        response_example="중복 등록",
        recommended_replies=("하나", "둘", "셋"),
    )
    monkeypatch.setattr(registry_module, "DETAILED_GRAPH_CONTRACTS", (contract,))
    monkeypatch.setattr(registry_module, "SCENARIOS", {duplicate.key: duplicate})

    with pytest.raises(RuntimeError, match="duplicate LangGraph scenario registration"):
        registry_module._build_flow_registry()


def test_chat_route_dispatches_detailed_registration(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.hospital.nodes.analyze_hospital_reservation_user_message",
        lambda conversation_state, user_message: {
            "intent": "reservation",
            "department": None,
            "date": None,
            "time": None,
            "user_action": "continue_collecting",
            "selected_time": None,
        },
    )

    response = TestClient(app).post(
        "/chat",
        json={
            "category": "예약",
            "title": "🏥 병원 예약",
            "description": "병원 예약 통화",
            "userMessage": "예약하고 싶습니다.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["simulation"] == {
        "mode": "simulation",
        "externalEffect": False,
    }
    assert body["scenarioState"]["scenario_key"] == "예약:병원 예약"
    assert body["conversationState"] == "asking_department"
