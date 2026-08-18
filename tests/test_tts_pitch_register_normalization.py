from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np
import pytest

from scripts.normalize_tts_pitch_register import normalize_pitch_register
from scripts.tts_audition_common import describe_wav_pitch


def test_pitch_register_normalization_preserves_duration_and_restores_target(tmp_path: Path):
    sample_rate = 24_000
    duration_seconds = 1
    source_frequency = 240.0
    target_frequency = 175.0
    samples = np.array(
        [
            math.sin(2 * math.pi * source_frequency * index / sample_rate)
            for index in range(sample_rate * duration_seconds)
        ],
        dtype=np.float32,
    )
    source_path = tmp_path / "source.wav"
    output_path = tmp_path / "normalized.wav"
    with wave.open(str(source_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes((samples * 16_000).astype("<i2").tobytes())

    scale = normalize_pitch_register(
        source_path,
        output_path,
        source_median_f0_hz=source_frequency,
        target_median_f0_hz=target_frequency,
    )

    source_pitch = describe_wav_pitch(source_path)
    output_pitch = describe_wav_pitch(output_path)
    assert scale == pytest.approx(target_frequency / source_frequency)
    assert source_pitch["medianF0Hz"] == pytest.approx(source_frequency, abs=1.0)
    assert output_pitch["medianF0Hz"] == pytest.approx(target_frequency, abs=1.0)
    with (
        wave.open(str(source_path), "rb") as source_wav,
        wave.open(str(output_path), "rb") as output_wav,
    ):
        assert output_wav.getnframes() == source_wav.getnframes()
        assert output_wav.getframerate() == source_wav.getframerate()
