from __future__ import annotations

import json
import math
import wave
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from scripts.analyze_aihub_mature_female_reference import (
    CLIPS_PER_SPEAKER,
    MINIMUM_SPEAKERS,
    build_reference_manifest,
    load_eligible_clips,
    select_balanced_clips,
    write_reference_manifest,
)


def _write_sine_wav(path: Path, *, frequency_hz: float) -> None:
    sample_rate = 16_000
    frame_count = 4_000
    samples = np.array(
        [
            math.sin(2 * math.pi * frequency_hz * index / sample_rate)
            for index in range(frame_count)
        ],
        dtype=np.float32,
    )
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes((samples * 16_000).astype("<i2").tobytes())


def _write_label(
    label_root: Path,
    audio_root: Path,
    *,
    speaker_number: int,
    clip_number: int,
    age: int,
    gender: str = "f",
    second_speaker: bool = False,
) -> None:
    speaker_id = f"speakerjj{speaker_number:04d}"
    stem = f"st_set1_{speaker_id}_{clip_number}"
    speakers = [
        {
            "speakerId": speaker_id,
            "gender": gender,
            "birthYear": float(2022 - age),
            "residenceProvince": "jj",
        }
    ]
    if second_speaker:
        speakers.append(
            {
                "speakerId": f"speakerjj{speaker_number + 1000:04d}",
                "gender": gender,
                "birthYear": float(2022 - age),
                "residenceProvince": "jj",
            }
        )
    payload = {
        "fileName": stem,
        "speaker": speakers,
        "script": {"speechType": "Speak"},
        "audio": {"recordDate": "20221121"},
    }
    (label_root / f"{stem}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    _write_sine_wav(audio_root / f"{stem}.wav", frequency_hz=145 + speaker_number)


def _write_eligible_dataset(label_root: Path, audio_root: Path) -> None:
    label_root.mkdir()
    audio_root.mkdir()
    for speaker_number in range(MINIMUM_SPEAKERS):
        for clip_number in range(CLIPS_PER_SPEAKER + 1):
            _write_label(
                label_root,
                audio_root,
                speaker_number=speaker_number,
                clip_number=clip_number,
                age=50 + speaker_number % 20,
            )


def test_reference_selection_is_balanced_and_manifest_is_anonymous(tmp_path: Path):
    label_root = tmp_path / "labels"
    audio_root = tmp_path / "audio"
    _write_eligible_dataset(label_root, audio_root)

    clips = load_eligible_clips(label_root, audio_root)
    selected = select_balanced_clips(clips)
    manifest = build_reference_manifest(clips, generated_at=datetime(2026, 8, 18, tzinfo=UTC))

    assert len(clips) == MINIMUM_SPEAKERS * (CLIPS_PER_SPEAKER + 1)
    assert len(selected) == MINIMUM_SPEAKERS * CLIPS_PER_SPEAKER
    assert manifest["coverage"] == {
        "eligibleSpeakers": MINIMUM_SPEAKERS,
        "selectedSpeakers": MINIMUM_SPEAKERS,
        "selectedClips": MINIMUM_SPEAKERS * CLIPS_PER_SPEAKER,
        "speakerCountByAgeBand": {"50s": 10, "60s": 10},
        "provinceCodes": ["jj"],
        "speechTypes": ["Speak"],
    }
    assert manifest["acousticReference"]["speakerMedianF0Hz"]["median"] == pytest.approx(
        154.5, abs=1.0
    )
    assert manifest["privacy"]["containsSpeakerIdentifiers"] is False
    serialized = json.dumps(manifest, ensure_ascii=False)
    assert "speakerjj" not in serialized
    assert "st_set1" not in serialized


def test_reference_rejects_too_few_distinct_speakers(tmp_path: Path):
    label_root = tmp_path / "labels"
    audio_root = tmp_path / "audio"
    label_root.mkdir()
    audio_root.mkdir()
    for speaker_number in range(MINIMUM_SPEAKERS - 1):
        _write_label(
            label_root,
            audio_root,
            speaker_number=speaker_number,
            clip_number=0,
            age=55,
        )

    clips = load_eligible_clips(label_root, audio_root)

    with pytest.raises(RuntimeError, match=f"At least {MINIMUM_SPEAKERS}"):
        select_balanced_clips(clips)


def test_reference_excludes_ineligible_and_multi_speaker_recordings(tmp_path: Path):
    label_root = tmp_path / "labels"
    audio_root = tmp_path / "audio"
    label_root.mkdir()
    audio_root.mkdir()
    _write_label(label_root, audio_root, speaker_number=1, clip_number=0, age=49)
    _write_label(
        label_root,
        audio_root,
        speaker_number=2,
        clip_number=0,
        age=55,
        gender="m",
    )
    _write_label(
        label_root,
        audio_root,
        speaker_number=3,
        clip_number=0,
        age=55,
        second_speaker=True,
    )

    with pytest.raises(RuntimeError, match="No eligible single-speaker female clips"):
        load_eligible_clips(label_root, audio_root)


def test_reference_output_is_never_silently_overwritten(tmp_path: Path):
    output = tmp_path / "reference.json"
    output.write_text("{}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Output already exists"):
        write_reference_manifest(output, {"referenceContractVersion": 1})
