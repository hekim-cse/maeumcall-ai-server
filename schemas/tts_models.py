from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from core.config import TTS_MAX_TEXT_LENGTH, TTS_MODEL_NAME, TTS_MODEL_REVISION
from services.tts.catalog import TTSVoiceId, TTSVoiceProfile


class TTSRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=TTS_MAX_TEXT_LENGTH)
    voice: TTSVoiceId


class TTSVoiceCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = "qwen3-tts"
    model: str = TTS_MODEL_NAME
    modelRevision: str = TTS_MODEL_REVISION
    language: str = "Korean"
    voices: list[TTSVoiceProfile]
