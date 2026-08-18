from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np
import pytest

from scripts.refine_tts_timing_and_prosody import _read_pcm16_wav, refine_timing_and_prosody
from scripts.tts_audition_common import describe_wav_pitch


def test_refinement_shortens_only_long_pauses_and_reduces_pitch_excursions(
    tmp_path: Path,
):
    sample_rate = 24_000

    def tone(frequency: float, duration_seconds: float) -> np.ndarray:
        frames = round(sample_rate * duration_seconds)
        return np.array(
            [math.sin(2 * math.pi * frequency * index / sample_rate) for index in range(frames)],
            dtype=np.float32,
        )

    source_samples = np.concatenate(
        [
            tone(155.0, 0.6),
            np.zeros(round(sample_rate * 0.5), dtype=np.float32),
            tone(205.0, 0.6),
        ]
    )
    source_path = tmp_path / "source.wav"
    output_path = tmp_path / "output.wav"
    with wave.open(str(source_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes((source_samples * 16_000).astype("<i2").tobytes())

    source_pitch = describe_wav_pitch(source_path)
    pause_changes = refine_timing_and_prosody(
        source_path,
        output_path,
        center_f0_hz=float(source_pitch["medianF0Hz"]),
        prosody_scale=0.8,
        pause_scale=0.65,
    )

    refined_pitch = describe_wav_pitch(output_path)
    source_spread = float(source_pitch["p75F0Hz"]) - float(source_pitch["p25F0Hz"])
    refined_spread = float(refined_pitch["p75F0Hz"]) - float(refined_pitch["p25F0Hz"])
    assert refined_spread < source_spread
    assert abs(float(refined_pitch["medianF0Hz"]) - float(source_pitch["medianF0Hz"])) < 1
    assert len(pause_changes) == 1
    assert pause_changes[0]["refinedDurationSeconds"] < pause_changes[0]["originalDurationSeconds"]
    with (
        wave.open(str(source_path), "rb") as source_wav,
        wave.open(str(output_path), "rb") as output_wav,
    ):
        assert output_wav.getnframes() < source_wav.getnframes()


def test_timing_refinement_rejects_non_pcm16_wav(tmp_path: Path):
    source_path = tmp_path / "pcm8.wav"
    with wave.open(str(source_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(1)
        wav_file.setframerate(24_000)
        wav_file.writeframes(bytes([128] * 240))

    with pytest.raises(
        ValueError,
        match="requires an uncompressed PCM 16-bit WAV file",
    ):
        _read_pcm16_wav(source_path)
