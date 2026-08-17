import pytest
from fastapi.testclient import TestClient

from main import app


pytestmark = pytest.mark.unit


def test_word_frequency_accepts_typed_turns():
    response = TestClient(app).post(
        "/analysis/wordfreq",
        json={
            "turns": [
                {"role": "user", "text": "음 오늘 일정 알려주세요"},
                {"role": "assistant", "text": "오늘 일정은 두 개입니다"},
            ],
            "scope": "user",
        },
    )

    assert response.status_code == 200
    assert response.json()["total_messages"] == 1
    assert response.json()["filler_count"] == 1


def test_word_frequency_rejects_unregistered_role_instead_of_inferring_it():
    response = TestClient(app).post(
        "/analysis/wordfreq",
        json={"turns": [{"role": "bot", "text": "안녕하세요"}]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"


def test_word_frequency_rejects_ambiguous_input_sources():
    response = TestClient(app).post(
        "/analysis/wordfreq",
        json={"messages": ["안녕하세요"], "turns": []},
    )

    assert response.status_code == 422
