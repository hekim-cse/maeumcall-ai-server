from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.auth import AuthenticatedUser, require_authenticated_user
from main import app
from services.tts.casting import ScenarioVoiceAssignment
from services.tts.catalog import TTSVoiceId
from services.tts.errors import TTSServiceError
from services.tts.provider import SynthesizedSpeech
from services.tts.service import get_tts_runtime

pytestmark = pytest.mark.unit


class TTSRuntimeDouble:
    def __init__(self) -> None:
        self.requests: list[tuple[str, ScenarioVoiceAssignment]] = []

    def probe(self) -> None:
        return None

    def synthesize(
        self,
        *,
        text: str,
        assignment: ScenarioVoiceAssignment,
    ) -> SynthesizedSpeech:
        self.requests.append((text, assignment))
        return SynthesizedSpeech(
            audio=b"RIFF-test-wave",
            media_type="audio/wav",
            sample_rate=24_000,
            voice=assignment.voice,
            provider=assignment.provider.value,
            model="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
            model_revision="fixed-revision",
        )


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def _authenticated_client(runtime: TTSRuntimeDouble) -> TestClient:
    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        uid="verified-user"
    )
    app.dependency_overrides[get_tts_runtime] = lambda: runtime
    return TestClient(app)


def test_tts_voice_catalog_exposes_all_verified_qwen_voices():
    response = TestClient(app).get("/tts/voices")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "qwen3-tts"
    assert body["language"] == "Korean"
    assert {voice["id"] for voice in body["voices"]} == {voice.value for voice in TTSVoiceId}
    assert [voice["id"] for voice in body["voices"] if voice["nativeKorean"]] == ["sohee"]


def test_tts_synthesis_requires_an_authenticated_session():
    response = TestClient(app).post(
        "/tts/synthesize",
        json={"text": "안녕하세요.", "voice": "sohee"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHORIZATION_REQUIRED"


def test_tts_synthesis_returns_audio_and_reproducibility_headers():
    runtime = TTSRuntimeDouble()
    response = _authenticated_client(runtime).post(
        "/tts/synthesize",
        json={"text": "안녕하세요.", "voice": "sohee"},
    )

    assert response.status_code == 200
    assert response.content == b"RIFF-test-wave"
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["x-tts-provider"] == "qwen3-tts"
    assert response.headers["x-tts-model-revision"] == "fixed-revision"
    assert response.headers["x-tts-voice"] == "sohee"
    assert response.headers["x-audio-sample-rate"] == "24000"
    assert response.headers["cache-control"] == "private, no-store"
    assert len(runtime.requests) == 1
    text, assignment = runtime.requests[0]
    assert text == "안녕하세요."
    assert assignment.voice == TTSVoiceId.SOHEE.value


def test_tts_synthesis_rejects_unknown_voice_before_provider_call():
    runtime = TTSRuntimeDouble()
    response = _authenticated_client(runtime).post(
        "/tts/synthesize",
        json={"text": "안녕하세요.", "voice": "unknown"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"
    assert runtime.requests == []


def test_tts_provider_failure_uses_typed_error_contract():
    class FailingTTSRuntime(TTSRuntimeDouble):
        def synthesize(
            self,
            *,
            text: str,
            assignment: ScenarioVoiceAssignment,
        ) -> SynthesizedSpeech:
            raise TTSServiceError(
                "TTS_SYNTHESIS_FAILED",
                "음성 합성을 완료하지 못했습니다.",
                status_code=502,
            )

    response = _authenticated_client(FailingTTSRuntime()).post(
        "/tts/synthesize",
        json={"text": "안녕하세요.", "voice": "sohee"},
    )

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "TTS_SYNTHESIS_FAILED",
            "message": "음성 합성을 완료하지 못했습니다.",
        }
    }


def test_scenario_synthesis_resolves_cast_v2_on_the_server():
    runtime = TTSRuntimeDouble()
    response = _authenticated_client(runtime).post(
        "/tts/scenario/synthesize",
        json={
            "text": "예약 날짜를 확인해 드릴게요.",
            "scenarioKey": "예약:병원 예약",
            "castVersion": 2,
        },
    )

    assert response.status_code == 200
    assert response.headers["x-tts-cast-version"] == "2"
    assert (
        response.headers["x-tts-scenario-key"]
        == "%EC%98%88%EC%95%BD:%EB%B3%91%EC%9B%90%20%EC%98%88%EC%95%BD"
    )
    assert response.headers["x-tts-role"] == "service_agent"
    assert response.headers["x-tts-provider"] == "qwen3-tts"
    assert response.headers["x-tts-voice"] == "ryan"
    assert len(runtime.requests) == 1
    _, assignment = runtime.requests[0]
    assert assignment.voice == "ryan"


def test_cast_v2_family_synthesis_requires_an_explicit_persona():
    runtime = TTSRuntimeDouble()
    response = _authenticated_client(runtime).post(
        "/tts/scenario/synthesize",
        json={
            "text": "오늘 하루는 어땠어?",
            "scenarioKey": "가족:안부인사",
            "castVersion": 2,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TTS_PERSONA_REQUIRED"
    assert runtime.requests == []


def test_cast_v2_family_mother_uses_the_approved_voice_clone():
    runtime = TTSRuntimeDouble()
    response = _authenticated_client(runtime).post(
        "/tts/scenario/synthesize",
        json={
            "text": "엄마한테 천천히 이야기해 봐.",
            "scenarioKey": "가족:안부인사",
            "castVersion": 2,
            "personaId": "mother",
        },
    )

    assert response.status_code == 200
    assert response.headers["x-tts-persona"] == "mother"
    assert response.headers["x-tts-role"] == "family_mother"
    assert response.headers["x-tts-provider"] == "qwen3-tts-voice-clone"


def test_scenario_synthesis_rejects_an_unsupported_cast_version():
    runtime = TTSRuntimeDouble()
    response = _authenticated_client(runtime).post(
        "/tts/scenario/synthesize",
        json={
            "text": "안녕하세요.",
            "scenarioKey": "예약:병원 예약",
            "castVersion": 99,
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TTS_CAST_VERSION_UNSUPPORTED"
    assert runtime.requests == []
