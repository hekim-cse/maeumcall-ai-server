# 📄 praat_voice_analysis.py  (오디오 분석 전용 모듈)

from __future__ import annotations
import math
import parselmouth
import numpy as np

def _comment_pitch(mean_pitch: float) -> str:
    return "평균 기본 주파수 측정값입니다."

def _comment_jitter(j: float) -> str:
    return "주기 간 주파수 변동 측정값입니다."

def _comment_shimmer(s: float) -> str:
    return "주기 간 진폭 변동 측정값입니다."


def _finite_or_zero(value: float) -> float:
    return value if math.isfinite(value) else 0.0

def analyze_audio(file_path: str) -> dict:
    # 기존 analyze_audio_to_features 코드 복사해서 사용
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
    mean_pitch = float(np.mean(f0)) if len(f0) > 0 else 0.0

    # Jitter/Shimmer (Praat-style)
    pp = parselmouth.praat.call(snd, "To PointProcess (periodic, cc)", 75, 500)
    jitter_local = _finite_or_zero(float(parselmouth.praat.call(pp, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)))
    shimmer_local = _finite_or_zero(float(parselmouth.praat.call([snd, pp], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)))

    return {
        "pitch":   {"mean": round(mean_pitch, 3),    "comment": _comment_pitch(mean_pitch)},
        "jitter":  {"value": round(jitter_local, 6), "comment": _comment_jitter(jitter_local)},
        "shimmer": {"value": round(shimmer_local, 6),"comment": _comment_shimmer(shimmer_local)},
    }
