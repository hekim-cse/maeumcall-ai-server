from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.auth import AuthenticatedUser, require_authenticated_user
from main import app
from services.tts.catalog import TTSVoiceId
from services.tts.errors import TTSServiceError
from services.tts.provider import SynthesizedSpeech
from services.tts.service import get_tts_provider

pytestmark = pytest.mark.unit


class TTSProviderDouble:
    def __init__(self) -> None:
        self.requests: list[tuple[str, TTSVoiceId]] = []

    def probe(self) -> None:
        return None

    def synthesize(self, *, text: str, voice: TTSVoiceId) -> SynthesizedSpeech:
        self.requests.append((text, voice))
        return SynthesizedSpeech(
            audio=b"RIFF-test-wave",
            media_type="audio/wav",
            sample_rate=24_000,
            voice=voice,
            provider="qwen3-tts",
            model="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
            model_revision="fixed-revision",
        )


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def _authenticated_client(provider: TTSProviderDouble) -> TestClient:
    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        uid="verified-user"
    )
    app.dependency_overrides[get_tts_provider] = lambda: provider
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
    provider = TTSProviderDouble()
    response = _authenticated_client(provider).post(
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
    assert provider.requests == [("안녕하세요.", TTSVoiceId.SOHEE)]


def test_tts_synthesis_rejects_unknown_voice_before_provider_call():
    provider = TTSProviderDouble()
    response = _authenticated_client(provider).post(
        "/tts/synthesize",
        json={"text": "안녕하세요.", "voice": "unknown"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"
    assert provider.requests == []


def test_tts_provider_failure_uses_typed_error_contract():
    class FailingTTSProvider(TTSProviderDouble):
        def synthesize(self, *, text: str, voice: TTSVoiceId) -> SynthesizedSpeech:
            raise TTSServiceError(
                "TTS_SYNTHESIS_FAILED",
                "음성 합성을 완료하지 못했습니다.",
                status_code=502,
            )

    response = _authenticated_client(FailingTTSProvider()).post(
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
