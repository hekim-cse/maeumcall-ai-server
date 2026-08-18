from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SynthesizedSpeech:
    audio: bytes
    media_type: str
    sample_rate: int
    voice: str
    provider: str
    model: str
    model_revision: str


class TTSProvider(Protocol):
    def probe(self) -> None: ...

    def synthesize(self, *, text: str, voice: str) -> SynthesizedSpeech: ...

    def unload(self) -> None: ...
