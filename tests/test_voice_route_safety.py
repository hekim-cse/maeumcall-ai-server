from __future__ import annotations

import os
import tempfile
from collections import defaultdict
from typing import Any, Mapping

import pytest
from fastapi.testclient import TestClient

from main import app
from core.auth import (
    AuthenticatedUser,
    optional_authenticated_user,
    require_authenticated_user,
)
from routes import voice_routes
from services import baseline_store


pytestmark = pytest.mark.unit


class BaselineRepositoryDouble:
    """Contract-level test double; production always uses PostgreSQL."""

    def __init__(self) -> None:
        self.baselines: dict[str, dict[str, Any]] = {}
        self.samples: dict[str, list[tuple[float, float, float]]] = defaultdict(list)

    async def get_baseline(self, user_key: str) -> dict[str, Any] | None:
        return self.baselines.get(user_key)

    async def update_welford(
        self, user_key: str, measurement: tuple[float, float, float]
    ) -> dict[str, Any]:
        value = baseline_store.calculate_welford(
            self.baselines.get(user_key), measurement
        )
        self.baselines[user_key] = value
        return value

    async def append_calibration_sample(
        self, user_key: str, measurement: tuple[float, float, float]
    ) -> dict[str, Any]:
        self.samples[user_key].append(measurement)
        values = self.samples[user_key]
        count = len(values)
        return {
            "pitchHz": sum(value[0] for value in values) / count,
            "pitchStdHz": 0.0,
            "jitterLocal": sum(value[1] for value in values) / count,
            "jitterStd": 0.0,
            "shimmerLocal": sum(value[2] for value in values) / count,
            "shimmerStd": 0.0,
            "samples": count,
            "ts": 1,
        }

    async def finalize_calibration(self, user_key: str) -> dict[str, Any] | None:
        values = self.samples.get(user_key, [])
        if not values:
            return None
        count = len(values)
        baseline = {
            "pitchHz": sum(value[0] for value in values) / count,
            "pitchStdHz": 0.0,
            "jitterLocal": sum(value[1] for value in values) / count,
            "jitterStd": 0.0,
            "shimmerLocal": sum(value[2] for value in values) / count,
            "shimmerStd": 0.0,
            "samples": count,
            "ts": 1,
        }
        self.baselines[user_key] = baseline
        self.samples.pop(user_key, None)
        return baseline

    async def clear_calibration(self, user_key: str) -> None:
        self.samples.pop(user_key, None)

    async def delete_subject(self, user_key: str) -> bool:
        existed = user_key in self.baselines or user_key in self.samples
        self.baselines.pop(user_key, None)
        self.samples.pop(user_key, None)
        return existed

    async def import_baseline(
        self, user_key: str, baseline: Mapping[str, Any]
    ) -> None:
        self.baselines[user_key] = dict(baseline)


@pytest.fixture(autouse=True)
def baseline_repository(monkeypatch):
    repository = BaselineRepositoryDouble()
    monkeypatch.setattr(
        baseline_store, "BASELINE_ID_HMAC_SECRET", "test-secret-" * 4
    )
    baseline_store.set_baseline_repository(repository)
    yield repository
    baseline_store.set_baseline_repository(None)


@pytest.fixture(autouse=True)
def authenticated_voice_user():
    user = AuthenticatedUser(uid="authenticated-user")

    async def require_user() -> AuthenticatedUser:
        return user

    async def optional_user() -> AuthenticatedUser:
        return user

    app.dependency_overrides[require_authenticated_user] = require_user
    app.dependency_overrides[optional_authenticated_user] = optional_user
    yield user
    app.dependency_overrides.pop(require_authenticated_user, None)
    app.dependency_overrides.pop(optional_authenticated_user, None)


def _analysis() -> dict[str, dict[str, float | str]]:
    return {
        "pitch": {"mean": 150.0, "comment": "measurement"},
        "jitter": {"value": 0.005, "comment": "measurement"},
        "shimmer": {"value": 0.01, "comment": "measurement"},
    }


def test_voice_route_rejects_invalid_mode_before_analysis():
    response = TestClient(app).post(
        "/voice/analyze",
        data={"mode": "unsupported"},
        files={"file": ("voice.wav", b"audio", "audio/wav")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VOICE_MODE_INVALID"


def test_voice_route_enforces_upload_limit(monkeypatch):
    monkeypatch.setattr(voice_routes, "AUDIO_UPLOAD_MAX_BYTES", 4)
    response = TestClient(app).post(
        "/voice/analyze",
        files={"file": ("voice.wav", b"12345", "audio/wav")},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "VOICE_FILE_TOO_LARGE"


def test_voice_route_never_uses_uploaded_path(monkeypatch):
    analyzed_paths: list[str] = []

    def fake_analyze(path: str) -> dict[str, Any]:
        analyzed_paths.append(path)
        return _analysis()

    monkeypatch.setattr(voice_routes, "analyze_audio", fake_analyze)
    response = TestClient(app).post(
        "/voice/analyze",
        files={"file": ("../../escape.wav", b"fake wav", "audio/wav")},
    )
    assert response.status_code == 200
    assert len(analyzed_paths) == 1
    assert os.path.dirname(analyzed_paths[0]) == tempfile.gettempdir()
    assert os.path.basename(analyzed_paths[0]).startswith("maeumcall_")
    assert not os.path.exists(analyzed_paths[0])


def test_calibration_samples_survive_requests_until_transactional_finalize(
    monkeypatch, baseline_repository
):
    monkeypatch.setattr(voice_routes, "analyze_audio", lambda path: _analysis())
    client = TestClient(app)

    for expected_samples in (1, 2):
        response = client.post(
            "/voice/analyze",
            data={"mode": "calibrate"},
            files={"file": ("voice.wav", b"audio", "audio/wav")},
        )
        assert response.status_code == 200
        assert response.json()["samples"] == expected_samples

    finalized = client.post("/voice/calibrate/finalize")
    assert finalized.status_code == 200
    assert finalized.json()["baseline"]["samples"] == 2
    user_key = baseline_store.pseudonymize_user_id("authenticated-user")
    assert user_key in baseline_repository.baselines
    assert user_key not in baseline_repository.samples


def test_calibration_reset_preserves_last_confirmed_baseline(baseline_repository):
    user_key = baseline_store.pseudonymize_user_id("authenticated-user")
    baseline_repository.baselines[user_key] = {"samples": 1}
    baseline_repository.samples[user_key].append((150.0, 0.005, 0.01))

    response = TestClient(app).post("/voice/calibrate/reset")
    assert response.status_code == 200
    assert user_key in baseline_repository.baselines
    assert user_key not in baseline_repository.samples


def test_finalize_requires_collected_samples():
    response = TestClient(app).post("/voice/calibrate/finalize")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VOICE_CALIBRATION_EMPTY"


def test_baseline_storage_refuses_plain_user_id_without_hmac_secret(monkeypatch):
    monkeypatch.setattr(baseline_store, "BASELINE_ID_HMAC_SECRET", "")
    response = TestClient(app).get("/voice/baseline")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "VOICE_BASELINE_SECURITY_NOT_CONFIGURED"


@pytest.mark.parametrize(
    "analysis",
    [
        {"pitch": {"mean": 0}, "jitter": {"value": 0.1}, "shimmer": {"value": 0.1}},
        {"pitch": {"mean": 120}, "jitter": {"value": -0.1}, "shimmer": {"value": 0.1}},
    ],
)
def test_invalid_voice_measurements_are_rejected(analysis):
    with pytest.raises(baseline_store.BaselineMeasurementError):
        baseline_store.extract_measurement(analysis)


def test_unmeasurable_voice_returns_a_typed_client_error(monkeypatch):
    from praat_voice_analysis import VoiceAnalysisError

    def reject_unvoiced_audio(path: str):
        raise VoiceAnalysisError(
            "VOICE_NO_VOICED_AUDIO",
            "목소리가 감지되지 않았습니다.",
        )

    monkeypatch.setattr(voice_routes, "analyze_audio", reject_unvoiced_audio)

    response = TestClient(app).post(
        "/voice/analyze",
        files={"file": ("voice.wav", b"audio", "audio/wav")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VOICE_NO_VOICED_AUDIO"
