from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class TTSVoiceId(StrEnum):
    AIDEN = "aiden"
    DYLAN = "dylan"
    ERIC = "eric"
    ONO_ANNA = "ono_anna"
    RYAN = "ryan"
    SERENA = "serena"
    SOHEE = "sohee"
    UNCLE_FU = "uncle_fu"
    VIVIAN = "vivian"


class TTSVoiceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: TTSVoiceId
    description: str
    nativeLanguage: str
    nativeKorean: bool


TTS_VOICE_CATALOG: tuple[TTSVoiceProfile, ...] = (
    TTSVoiceProfile(
        id=TTSVoiceId.AIDEN,
        description="맑은 중음역의 밝은 남성 음색",
        nativeLanguage="English",
        nativeKorean=False,
    ),
    TTSVoiceProfile(
        id=TTSVoiceId.DYLAN,
        description="또렷하고 자연스러운 젊은 남성 음색",
        nativeLanguage="Chinese (Beijing)",
        nativeKorean=False,
    ),
    TTSVoiceProfile(
        id=TTSVoiceId.ERIC,
        description="약간 허스키하고 생동감 있는 남성 음색",
        nativeLanguage="Chinese (Sichuan)",
        nativeKorean=False,
    ),
    TTSVoiceProfile(
        id=TTSVoiceId.ONO_ANNA,
        description="가볍고 경쾌한 여성 음색",
        nativeLanguage="Japanese",
        nativeKorean=False,
    ),
    TTSVoiceProfile(
        id=TTSVoiceId.RYAN,
        description="리듬감 있고 역동적인 남성 음색",
        nativeLanguage="English",
        nativeKorean=False,
    ),
    TTSVoiceProfile(
        id=TTSVoiceId.SERENA,
        description="따뜻하고 부드러운 젊은 여성 음색",
        nativeLanguage="Chinese",
        nativeKorean=False,
    ),
    TTSVoiceProfile(
        id=TTSVoiceId.SOHEE,
        description="감정 표현이 풍부하고 따뜻한 한국어 여성 음색",
        nativeLanguage="Korean",
        nativeKorean=True,
    ),
    TTSVoiceProfile(
        id=TTSVoiceId.UNCLE_FU,
        description="낮고 차분한 중년 남성 음색",
        nativeLanguage="Chinese",
        nativeKorean=False,
    ),
    TTSVoiceProfile(
        id=TTSVoiceId.VIVIAN,
        description="밝고 선명한 젊은 여성 음색",
        nativeLanguage="Chinese",
        nativeKorean=False,
    ),
)
