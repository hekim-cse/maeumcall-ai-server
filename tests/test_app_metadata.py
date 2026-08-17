import pytest
import uuid
from fastapi.testclient import TestClient

from main import app


pytestmark = pytest.mark.unit


def test_app_metadata_and_health_contract():
    client = TestClient(app)

    health = client.get("/health")
    root = client.get("/")

    assert health.status_code == 200
    uuid.UUID(health.headers["X-Request-ID"])
    assert health.json() == {"ok": True}
    assert root.status_code == 200
    assert root.json() == {
        "name": "MaeumCall AI Server",
        "version": "2.1.0",
        "docs": "/docs",
    }


def test_readiness_reports_each_runtime_dependency():
    client = TestClient(app)

    response = client.get("/health/ready")

    assert response.status_code in {200, 503}
    body = response.json()
    assert body["status"] in {"ready", "not_ready"}
    assert set(body["components"]) == {
        "openai",
        "local_nlu",
        "voice_baseline_security",
        "postgresql",
        "ffmpeg",
        "reservation_availability",
        "authentication",
    }


@pytest.mark.parametrize("path", ["/suggest", "/improve", "/analyze"])
def test_legacy_api_aliases_are_not_exposed(path: str):
    response = TestClient(app).post(path)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "HTTP_ERROR"
