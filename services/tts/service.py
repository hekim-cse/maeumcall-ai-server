from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from functools import lru_cache

from core.config import (
    TTS_BARK_MODEL_NAME,
    TTS_BARK_MODEL_REVISION,
    TTS_DEVICE,
    TTS_DTYPE,
    TTS_ENABLED,
    TTS_LOCAL_FILES_ONLY,
    TTS_MAX_NEW_TOKENS,
    TTS_MODEL_NAME,
    TTS_MODEL_REVISION,
    TTS_VOICE_CLONE_MANIFEST_PATH,
)
from services.tts.bark_provider import BarkTTSProvider
from services.tts.casting import ScenarioVoiceAssignment, TTSProviderId
from services.tts.errors import TTSServiceError
from services.tts.provider import SynthesizedSpeech, TTSProvider
from services.tts.qwen_provider import QwenTTSProvider
from services.tts.qwen_voice_clone_provider import QwenVoiceCloneTTSProvider

ProviderFactory = Callable[[], TTSProvider]


class TTSRuntime:
    """Own one active local model and serialize cross-provider model switching."""

    def __init__(self, factories: Mapping[TTSProviderId, ProviderFactory]) -> None:
        self._factories = dict(factories)
        self._active_provider_id: TTSProviderId | None = None
        self._active_provider: TTSProvider | None = None
        self._lock = threading.Lock()

    def _activate(self, provider_id: TTSProviderId) -> TTSProvider:
        if self._active_provider_id is provider_id and self._active_provider is not None:
            return self._active_provider
        factory = self._factories.get(provider_id)
        if factory is None:
            raise TTSServiceError(
                "TTS_PROVIDER_UNAVAILABLE",
                "선택된 음성 공급자를 현재 실행 환경에서 사용할 수 없습니다.",
                status_code=503,
            )
        provider = factory()
        if self._active_provider is not None:
            self._active_provider.unload()
        self._active_provider_id = provider_id
        self._active_provider = provider
        return provider

    def synthesize(
        self,
        *,
        text: str,
        assignment: ScenarioVoiceAssignment,
    ) -> SynthesizedSpeech:
        if not self._lock.acquire(blocking=False):
            raise TTSServiceError(
                "TTS_BUSY",
                "다른 음성 합성 요청을 처리하고 있습니다. 잠시 후 다시 시도해 주세요.",
                status_code=429,
            )
        try:
            provider = self._activate(assignment.provider)
            return provider.synthesize(text=text, voice=assignment.voice)
        finally:
            self._lock.release()

    def probe(self) -> None:
        if not self._lock.acquire(blocking=False):
            raise TTSServiceError(
                "TTS_BUSY",
                "음성 합성 실행 환경을 확인할 수 없습니다.",
                status_code=503,
            )
        try:
            for provider_id in self._factories:
                provider = self._activate(provider_id)
                provider.probe()
                provider.unload()
        finally:
            if self._active_provider is not None:
                self._active_provider.unload()
            self._active_provider_id = None
            self._active_provider = None
            self._lock.release()


def _build_tts_runtime() -> TTSRuntime:
    return TTSRuntime(
        {
            TTSProviderId.QWEN3_TTS: lambda: QwenTTSProvider(
                model_name=TTS_MODEL_NAME,
                model_revision=TTS_MODEL_REVISION,
                local_files_only=TTS_LOCAL_FILES_ONLY,
                device=TTS_DEVICE,
                dtype=TTS_DTYPE,
                max_new_tokens=TTS_MAX_NEW_TOKENS,
            ),
            TTSProviderId.BARK_SMALL: lambda: BarkTTSProvider(
                model_name=TTS_BARK_MODEL_NAME,
                model_revision=TTS_BARK_MODEL_REVISION,
                local_files_only=TTS_LOCAL_FILES_ONLY,
                device=TTS_DEVICE,
            ),
            TTSProviderId.QWEN3_TTS_VOICE_CLONE: lambda: QwenVoiceCloneTTSProvider(
                manifest_path=TTS_VOICE_CLONE_MANIFEST_PATH,
                local_files_only=TTS_LOCAL_FILES_ONLY,
                device=TTS_DEVICE,
                dtype=TTS_DTYPE,
            ),
        }
    )


@lru_cache(maxsize=1)
def get_tts_runtime() -> TTSRuntime:
    if not TTS_ENABLED:
        raise TTSServiceError(
            "TTS_NOT_ENABLED",
            "음성 합성 기능이 활성화되지 않았습니다.",
            status_code=503,
        )
    return _build_tts_runtime()


@lru_cache(maxsize=1)
def tts_runtime_ready() -> bool:
    if not TTS_ENABLED:
        return True
    try:
        get_tts_runtime().probe()
    except TTSServiceError:
        return False
    return True
