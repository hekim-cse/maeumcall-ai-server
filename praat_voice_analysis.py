# 📄 praat_voice_analysis.py  (오디오 분석 전용 모듈)

from __future__ import annotations

import math

import numpy as np
import parselmouth


class VoiceAnalysisError(ValueError):
    def __init__(self, code: str, public_message: str):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message


def _comment_pitch(mean_pitch: float) -> str:
    return "평균 기본 주파수 측정값입니다."


def _comment_jitter(j: float) -> str:
    return "주기 간 주파수 변동 측정값입니다."


def _comment_shimmer(s: float) -> str:
    return "주기 간 진폭 변동 측정값입니다."


def _require_measurement(value: float, *, name: str, positive: bool) -> float:
    if not math.isfinite(value) or (positive and value <= 0) or value < 0:
        raise VoiceAnalysisError(
            "VOICE_MEASUREMENT_UNAVAILABLE",
            f"음성에서 유효한 {name} 측정값을 얻지 못했습니다. "
            "더 길고 선명하게 다시 말해 주세요.",
        )
    return value


def analyze_audio(file_path: str) -> dict:
    """
    반환 스키마(서버-클라 공통):
    {
      "pitch":   {"mean": float, "comment": str},
      "jitter":  {"value": float, "comment": str},
      "shimmer": {"value": float, "comment": str}
    }
    """
    snd = parselmouth.Sound(file_path)

    # Pitch
    pitch_obj = snd.to_pitch()
    f0 = pitch_obj.selected_array["frequency"]
    f0 = f0[f0 != 0]
    if len(f0) == 0:
        raise VoiceAnalysisError(
            "VOICE_NO_VOICED_AUDIO",
            "목소리가 감지되지 않았습니다. "
            "주변 소음을 줄이고 다시 말해 주세요.",
        )
    mean_pitch = _require_measurement(
        float(np.mean(f0)), name="음높이", positive=True
    )

    # Jitter/Shimmer (Praat-style)
    pp = parselmouth.praat.call(snd, "To PointProcess (periodic, cc)", 75, 500)
    jitter_local = _require_measurement(
        float(
            parselmouth.praat.call(
                pp, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3
            )
        ),
        name="주파수 변동",
        positive=False,
    )
    shimmer_local = _require_measurement(
        float(
            parselmouth.praat.call(
                [snd, pp],
                "Get shimmer (local)",
                0,
                0,
                0.0001,
                0.02,
                1.3,
                1.6,
            )
        ),
        name="진폭 변동",
        positive=False,
    )

    return {
        "pitch": {
            "mean": round(mean_pitch, 3),
            "comment": _comment_pitch(mean_pitch),
        },
        "jitter": {
            "value": round(jitter_local, 6),
            "comment": _comment_jitter(jitter_local),
        },
        "shimmer": {
            "value": round(shimmer_local, 6),
            "comment": _comment_shimmer(shimmer_local),
        },
    }
