import pytest
from fastapi.testclient import TestClient

from main import app


pytestmark = pytest.mark.unit


def test_app_metadata_and_health_contract():
    client = TestClient(app)

    health = client.get("/health")
    root = client.get("/")

    assert health.status_code == 200
    assert health.json() == {"ok": True}
    assert root.status_code == 200
    assert root.json() == {
        "name": "MaeumCall AI Server",
        "version": "2.0.0",
        "docs": "/docs",
    }
