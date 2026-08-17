from __future__ import annotations

from functools import lru_cache

from core.config import (
    TTS_DEVICE,
    TTS_DTYPE,
    TTS_ENABLED,
    TTS_LOCAL_FILES_ONLY,
    TTS_MAX_NEW_TOKENS,
    TTS_MODEL_NAME,
    TTS_MODEL_REVISION,
)
from services.tts.errors import TTSServiceError
from services.tts.provider import TTSProvider
from services.tts.qwen_provider import QwenTTSProvider


@lru_cache(maxsize=1)
def get_tts_provider() -> TTSProvider:
    if not TTS_ENABLED:
        raise TTSServiceError(
            "TTS_NOT_ENABLED",
            "음성 합성 기능이 활성화되지 않았습니다.",
            status_code=503,
        )
    return QwenTTSProvider(
        model_name=TTS_MODEL_NAME,
        model_revision=TTS_MODEL_REVISION,
        local_files_only=TTS_LOCAL_FILES_ONLY,
        device=TTS_DEVICE,
        dtype=TTS_DTYPE,
        max_new_tokens=TTS_MAX_NEW_TOKENS,
    )


@lru_cache(maxsize=1)
def tts_runtime_ready() -> bool:
    if not TTS_ENABLED:
        return True
    try:
        get_tts_provider().probe()
    except TTSServiceError:
        return False
    return True
