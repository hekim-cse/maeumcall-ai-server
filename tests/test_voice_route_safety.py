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
    assert response.json()["error"]["code"] == "VOICE_MODE_INVALID"


def test_voice_route_enforces_upload_limit(monkeypatch):
    monkeypatch.setattr(voice_routes, "AUDIO_UPLOAD_MAX_BYTES", 4)
    client = TestClient(app)

    response = client.post(
        "/voice/analyze",
        files={"file": ("voice.wav", b"12345", "audio/wav")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "VOICE_FILE_TOO_LARGE"


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
    monkeypatch.setattr(baseline_store, "BASELINE_ID_HMAC_SECRET", "test-secret-" * 4)
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
    persisted = (tmp_path / "baseline.json").read_text("utf-8")
    assert "voice-user" not in persisted
    assert "user_hmac_sha256:" in persisted
    baseline_store.CALIB_CACHE.clear()


def test_corrupted_baseline_store_is_not_treated_as_empty(monkeypatch, tmp_path):
    path = tmp_path / "baseline.json"
    path.write_text("not-json", encoding="utf-8")
    monkeypatch.setattr(baseline_store, "DB_PATH", path)

    with pytest.raises(baseline_store.BaselineStoreError):
        baseline_store.load_db()


def test_calibration_reset_preserves_last_confirmed_baseline(monkeypatch, tmp_path):
    monkeypatch.setattr(baseline_store, "DB_PATH", tmp_path / "baseline.json")
    monkeypatch.setattr(baseline_store, "BASELINE_ID_HMAC_SECRET", "test-secret-" * 4)
    baseline_store.CALIB_CACHE.clear()
    analysis = {
        "pitch": {"mean": 150.0, "comment": "measurement"},
        "jitter": {"value": 0.005, "comment": "measurement"},
        "shimmer": {"value": 0.01, "comment": "measurement"},
    }
    baseline_store.update_baseline_persisted("voice-user", analysis)
    baseline_store.append_calib_sample("voice-user", analysis)

    response = TestClient(app).post(
        "/voice/calibrate/reset",
        data={"user_id": "voice-user"},
    )

    assert response.status_code == 200
    assert baseline_store.get_persisted_baseline("voice-user") is not None
    user_key = baseline_store.pseudonymize_user_id("voice-user")
    assert user_key not in baseline_store.CALIB_CACHE


def test_finalize_requires_collected_samples(monkeypatch, tmp_path):
    monkeypatch.setattr(baseline_store, "DB_PATH", tmp_path / "baseline.json")
    monkeypatch.setattr(baseline_store, "BASELINE_ID_HMAC_SECRET", "test-secret-" * 4)
    baseline_store.CALIB_CACHE.clear()

    response = TestClient(app).post(
        "/voice/calibrate/finalize",
        data={"user_id": "voice-user"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VOICE_CALIBRATION_EMPTY"


def test_baseline_storage_refuses_plain_user_id_without_hmac_secret(monkeypatch, tmp_path):
    monkeypatch.setattr(baseline_store, "DB_PATH", tmp_path / "baseline.json")
    monkeypatch.setattr(baseline_store, "BASELINE_ID_HMAC_SECRET", "")

    response = TestClient(app).get(
        "/voice/baseline",
        params={"user_id": "real-account-id"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "VOICE_BASELINE_SECURITY_NOT_CONFIGURED"
    assert not (tmp_path / "baseline.json").exists()
