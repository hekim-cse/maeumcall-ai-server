import pytest
from fastapi.testclient import TestClient

from main import app
from services.flow.scenario import graph as scenario_graph


pytestmark = pytest.mark.unit


def _scenario_payload():
    return {
        "category": "친구",
        "title": "심심해서 거는 전화",
        "description": "편한 통화",
        "userMessage": "안녕",
    }


def test_invalid_model_output_returns_validation_error(monkeypatch):
    monkeypatch.setattr(scenario_graph, "complete_json_messages", lambda messages: "JSON이 아닌 출력")

    response = TestClient(app).post("/chat", json=_scenario_payload())

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "AI_RESPONSE_VALIDATION_FAILED",
            "message": "AI 응답을 검증하지 못했습니다. 요청을 다시 시도해 주세요.",
        }
    }


def test_disabled_local_model_returns_provider_unavailable(monkeypatch):
    monkeypatch.setattr("llm.huggingface_provider.HF_LOCAL_MODEL_ENABLED", False)
    payload = {
        "category": "예약",
        "title": "병원 예약",
        "description": "병원 예약 통화",
        "userMessage": "내일 예약하고 싶습니다.",
    }

    response = TestClient(app).post("/chat", json=payload)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_PROVIDER_UNAVAILABLE"


def test_unregistered_scenario_returns_contract_error():
    payload = {
        "category": "기타",
        "title": "등록되지 않은 상황",
        "description": "",
        "userMessage": "안녕하세요.",
    }

    response = TestClient(app).post("/chat", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_SCENARIO"
