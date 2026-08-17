from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from services.tts.catalog import TTSVoiceId


@dataclass(frozen=True)
class SynthesizedSpeech:
    audio: bytes
    media_type: str
    sample_rate: int
    voice: TTSVoiceId
    provider: str
    model: str
    model_revision: str


class TTSProvider(Protocol):
    def probe(self) -> None: ...

    def synthesize(self, *, text: str, voice: TTSVoiceId) -> SynthesizedSpeech: ...
