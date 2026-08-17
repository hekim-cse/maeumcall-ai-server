import pytest
from fastapi.testclient import TestClient

from main import app


pytestmark = pytest.mark.unit


def test_call_setup_returns_versioned_registered_scenario_plan():
    response = TestClient(app).post(
        "/call/setup",
        json={
            "contract_version": 1,
            "category": "예약",
            "title": "🏥 병원 예약",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == 1
    assert body["scenario_key"] == "예약:병원 예약"
    assert body["direction"] == "outgoing"
    assert body["who_starts"] == "agent"


def test_call_setup_rejects_unregistered_scenario():
    response = TestClient(app).post(
        "/call/setup",
        json={
            "contract_version": 1,
            "category": "예약",
            "title": "등록되지 않은 예약",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_SCENARIO"


def test_call_setup_rejects_unsupported_contract_version():
    response = TestClient(app).post(
        "/call/setup",
        json={
            "contract_version": 2,
            "category": "예약",
            "title": "병원 예약",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CALL_SETUP_VERSION_UNSUPPORTED"


def test_call_setup_requires_contract_version():
    response = TestClient(app).post(
        "/call/setup",
        json={"category": "예약", "title": "병원 예약"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"
