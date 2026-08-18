from __future__ import annotations

from dataclasses import dataclass

import pytest
from prometheus_client import REGISTRY

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
    metric_labels = {
        "provider": "qwen3-tts",
        "model_state": "cold_start",
        "outcome": "success",
    }
    attempts_before = (
        REGISTRY.get_sample_value(
            "maeumcall_tts_synthesis_attempts_total",
            metric_labels,
        )
        or 0.0
    )
    duration_labels = {**metric_labels, "phase": "total"}
    durations_before = (
        REGISTRY.get_sample_value(
            "maeumcall_tts_synthesis_duration_seconds_count",
            duration_labels,
        )
        or 0.0
    )
    times = iter([10.0, 10.25, 12.75, 20.0, 20.01, 21.0])
    runtime = TTSRuntime(
        {TTSProviderId.QWEN3_TTS: lambda: qwen},
        clock=lambda: next(times),
    )

    first = runtime.synthesize(
        text="첫 번째",
        assignment=_assignment(TTSProviderId.QWEN3_TTS, "ryan"),
    )
    second = runtime.synthesize(
        text="두 번째",
        assignment=_assignment(TTSProviderId.QWEN3_TTS, "serena"),
    )

    assert first.speech.audio == "첫 번째".encode()
    assert first.timing.model_state == "cold_start"
    assert first.timing.transition_seconds == pytest.approx(0.25)
    assert first.timing.synthesis_seconds == pytest.approx(2.5)
    assert first.timing.total_seconds == pytest.approx(2.75)
    assert second.speech.voice == "serena"
    assert second.timing.model_state == "warm"
    assert qwen.unload_count == 0
    assert REGISTRY.get_sample_value(
        "maeumcall_tts_synthesis_attempts_total",
        metric_labels,
    ) == attempts_before + 1
    assert REGISTRY.get_sample_value(
        "maeumcall_tts_synthesis_duration_seconds_count",
        duration_labels,
    ) == durations_before + 1


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
    assert result.speech.provider == "bark-small"
    assert result.timing.model_state == "provider_switch"


def test_runtime_rejects_a_provider_without_an_operational_factory():
    runtime = TTSRuntime({})

    with pytest.raises(TTSServiceError) as exc_info:
        runtime.synthesize(
            text="이전 배역",
            assignment=_assignment(TTSProviderId.NVIDIA_MAGPIE, "sofia"),
        )

    assert exc_info.value.code == "TTS_PROVIDER_UNAVAILABLE"
