import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from main import app
from routes import voice_routes
from services import baseline_store


pytestmark = pytest.mark.unit


def test_voice_route_rejects_invalid_mode_before_analysis():
    client = TestClient(app)

    response = client.post(
        "/voice/analyze",
        data={"mode": "unsupported"},
        files={"file": ("voice.wav", b"audio", "audio/wav")},
    )

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_mode"


def test_voice_route_enforces_upload_limit(monkeypatch):
    monkeypatch.setattr(voice_routes, "AUDIO_UPLOAD_MAX_BYTES", 4)
    client = TestClient(app)

    response = client.post(
        "/voice/analyze",
        files={"file": ("voice.wav", b"12345", "audio/wav")},
    )

    assert response.status_code == 413
    assert response.json()["error"] == "file_too_large"


def test_voice_route_never_uses_uploaded_path(monkeypatch):
    analyzed_paths = []

    def fake_analyze(path):
        analyzed_paths.append(path)
        return {
            "pitch": {"mean": 150.0, "comment": "ok"},
            "jitter": {"value": 0.005, "comment": "ok"},
            "shimmer": {"value": 0.01, "comment": "ok"},
        }

    monkeypatch.setattr(voice_routes, "analyze_audio", fake_analyze)
    client = TestClient(app)

    response = client.post(
        "/voice/analyze",
        files={"file": ("../../escape.wav", b"fake wav", "audio/wav")},
    )

    assert response.status_code == 200
    assert len(analyzed_paths) == 1
    assert os.path.dirname(analyzed_paths[0]) == tempfile.gettempdir()
    assert os.path.basename(analyzed_paths[0]).startswith("maeumcall_")
    assert not os.path.exists(analyzed_paths[0])


def test_default_calibration_strategy_accumulates_until_finalize(monkeypatch, tmp_path):
    monkeypatch.setattr(baseline_store, "DB_PATH", tmp_path / "baseline.json")
    baseline_store.CALIB_CACHE.clear()
    monkeypatch.setattr(
        voice_routes,
        "analyze_audio",
        lambda path: {
            "pitch": {"mean": 150.0, "comment": "measurement"},
            "jitter": {"value": 0.005, "comment": "measurement"},
            "shimmer": {"value": 0.01, "comment": "measurement"},
        },
    )
    client = TestClient(app)

    for expected_samples in (1, 2):
        response = client.post(
            "/voice/analyze",
            data={"mode": "calibrate", "user_id": "voice-user"},
            files={"file": ("voice.wav", b"audio", "audio/wav")},
        )
        assert response.status_code == 200
        assert response.json()["samples"] == expected_samples

    finalized = client.post(
        "/voice/calibrate/finalize",
        data={"user_id": "voice-user"},
    )

    assert finalized.status_code == 200
    assert finalized.json()["ok"] is True
    assert finalized.json()["baseline"]["samples"] == 2
    baseline_store.CALIB_CACHE.clear()


def test_corrupted_baseline_store_is_not_treated_as_empty(monkeypatch, tmp_path):
    path = tmp_path / "baseline.json"
    path.write_text("not-json", encoding="utf-8")
    monkeypatch.setattr(baseline_store, "DB_PATH", path)

    with pytest.raises(baseline_store.BaselineStoreError):
        baseline_store.load_db()
