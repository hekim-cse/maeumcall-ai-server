# 📄 praat_voice_analysis.py  (오디오 분석 전용 모듈)

from __future__ import annotations
import parselmouth
import numpy as np

def _comment_pitch(mean_pitch: float) -> str:
    if mean_pitch < 100:
        return "목소리가 다소 낮고 소극적으로 들릴 수 있어요."
    if mean_pitch > 250:
        return "목소리가 다소 높아 불안하게 느껴질 수 있어요."
    return "적절한 음 높이입니다."

def _comment_jitter(j: float) -> str:
    if j < 0.005:
        return "목소리에 떨림이 거의 없습니다."
    if j < 0.01:
        return "조금의 떨림이 있지만 자연스러운 수준이에요."
    return "떨림이 다소 감지됩니다. 긴장했을 수 있어요."

def _comment_shimmer(s: float) -> str:
    if s < 0.01:
        return "목소리의 세기가 안정적이에요."
    if s < 0.03:
        return "약간의 강도 흔들림이 있지만 괜찮아요."
    return "강도 변화가 크네요. 자신감이 부족해 보일 수 있어요."

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
    jitter_local = float(parselmouth.praat.call(pp, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3))
    shimmer_local = float(parselmouth.praat.call([snd, pp], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6))

    return {
        "pitch":   {"mean": round(mean_pitch, 3),    "comment": _comment_pitch(mean_pitch)},
        "jitter":  {"value": round(jitter_local, 6), "comment": _comment_jitter(jitter_local)},
        "shimmer": {"value": round(shimmer_local, 6),"comment": _comment_shimmer(shimmer_local)},
    }