from __future__ import annotations

from dataclasses import dataclass

import pytest

from services.tts.casting import ScenarioVoiceAssignment, TTSProviderId
from services.tts.errors import TTSServiceError
from services.tts.provider import SynthesizedSpeech
from services.tts.service import TTSRuntime

pytestmark = pytest.mark.unit


@dataclass
class ProviderDouble:
    provider_id: TTSProviderId
    unload_count: int = 0

    def probe(self) -> None:
        return None

    def synthesize(self, *, text: str, voice: str) -> SynthesizedSpeech:
        return SynthesizedSpeech(
            audio=text.encode(),
            media_type="audio/wav",
            sample_rate=24_000,
            voice=voice,
            provider=self.provider_id.value,
            model="fixed-model",
            model_revision="fixed-revision",
        )

    def unload(self) -> None:
        self.unload_count += 1


def _assignment(provider: TTSProviderId, voice: str) -> ScenarioVoiceAssignment:
    return ScenarioVoiceAssignment(provider=provider, voice=voice, role_id="test_role")


def test_runtime_reuses_the_active_provider_for_consecutive_requests():
    qwen = ProviderDouble(TTSProviderId.QWEN3_TTS)
    runtime = TTSRuntime({TTSProviderId.QWEN3_TTS: lambda: qwen})

    first = runtime.synthesize(
        text="첫 번째",
        assignment=_assignment(TTSProviderId.QWEN3_TTS, "ryan"),
    )
    second = runtime.synthesize(
        text="두 번째",
        assignment=_assignment(TTSProviderId.QWEN3_TTS, "serena"),
    )

    assert first.audio == "첫 번째".encode()
    assert second.voice == "serena"
    assert qwen.unload_count == 0


def test_runtime_unloads_the_previous_model_before_provider_switch():
    qwen = ProviderDouble(TTSProviderId.QWEN3_TTS)
    bark = ProviderDouble(TTSProviderId.BARK_SMALL)
    runtime = TTSRuntime(
        {
            TTSProviderId.QWEN3_TTS: lambda: qwen,
            TTSProviderId.BARK_SMALL: lambda: bark,
        }
    )

    runtime.synthesize(
        text="상담원",
        assignment=_assignment(TTSProviderId.QWEN3_TTS, "ryan"),
    )
    result = runtime.synthesize(
        text="회사",
        assignment=_assignment(TTSProviderId.BARK_SMALL, "ko_speaker_5"),
    )

    assert qwen.unload_count == 1
    assert bark.unload_count == 0
    assert result.provider == "bark-small"


def test_runtime_rejects_a_provider_without_an_operational_factory():
    runtime = TTSRuntime({})

    with pytest.raises(TTSServiceError) as exc_info:
        runtime.synthesize(
            text="이전 배역",
            assignment=_assignment(TTSProviderId.NVIDIA_MAGPIE, "sofia"),
        )

    assert exc_info.value.code == "TTS_PROVIDER_UNAVAILABLE"
