from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import wave
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from scripts.tts_audition_common import describe_wav_pitch

DATASET_ID = 71558
DATASET_NAME = "중·노년층 한국어 방언 데이터 (충청도, 전라도, 제주도)"
DATASET_URL = "https://aihub.or.kr/aihubdata/data/view.do?currMenu=115&topMenu=100&dataSetSn=71558"
REFERENCE_CONTRACT_VERSION = 1
TARGET_GENDER = "f"
TARGET_MIN_AGE = 50
TARGET_MAX_AGE = 69
MINIMUM_SPEAKERS = 20
CLIPS_PER_SPEAKER = 3
SELECTION_SEED = "maeum-call-mature-female-reference-v1"


@dataclass(frozen=True)
class ReferenceClip:
    speaker_id: str
    age: int
    province: str
    speech_type: str
    stem: str
    label_path: Path
    audio_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a privacy-preserving acoustic reference from AI Hub dataset 71558. "
            "Only aggregate statistics are written."
        )
    )
    parser.add_argument("--label-root", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _require_mapping(value: Any, *, field: str, path: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected object at {field}: {path}")
    return value


def _require_list(value: Any, *, field: str, path: Path) -> list[Any]:
    if not isinstance(value, list):
        raise RuntimeError(f"Expected array at {field}: {path}")
    return value


def _require_string(value: Any, *, field: str, path: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Expected non-empty string at {field}: {path}")
    return value.strip()


def _require_integer_number(value: Any, *, field: str, path: Path) -> int:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise RuntimeError(f"Expected number at {field}: {path}")
    number = float(value)
    if not number.is_integer():
        raise RuntimeError(f"Expected integer-valued number at {field}: {path}")
    return int(number)


def _index_audio(audio_root: Path) -> dict[str, Path]:
    audio_paths = sorted(audio_root.rglob("*.wav"))
    if not audio_paths:
        raise RuntimeError(f"No WAV files found under audio root: {audio_root}")

    index: dict[str, Path] = {}
    for path in audio_paths:
        if path.stem in index:
            raise RuntimeError(f"Duplicate WAV stem in audio root: {path.stem}")
        index[path.stem] = path
    return index


def _load_reference_clip(label_path: Path, audio_index: dict[str, Path]) -> ReferenceClip | None:
    try:
        payload = json.loads(label_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Invalid JSON label: {label_path}") from error

    root = _require_mapping(payload, field="$", path=label_path)
    speakers = _require_list(root.get("speaker"), field="speaker", path=label_path)
    if len(speakers) != 1:
        return None

    speaker = _require_mapping(speakers[0], field="speaker[0]", path=label_path)
    gender = _require_string(speaker.get("gender"), field="speaker[0].gender", path=label_path)
    birth_year = _require_integer_number(
        speaker.get("birthYear"), field="speaker[0].birthYear", path=label_path
    )
    audio = _require_mapping(root.get("audio"), field="audio", path=label_path)
    record_date = _require_string(
        audio.get("recordDate"), field="audio.recordDate", path=label_path
    )
    if len(record_date) != 8 or not record_date.isdigit():
        raise RuntimeError(f"Expected YYYYMMDD at audio.recordDate: {label_path}")
    age = int(record_date[:4]) - birth_year
    if gender != TARGET_GENDER or not TARGET_MIN_AGE <= age <= TARGET_MAX_AGE:
        return None

    file_name = _require_string(root.get("fileName"), field="fileName", path=label_path)
    if Path(file_name).name != file_name:
        raise RuntimeError(f"fileName must not contain a directory: {label_path}")
    stem = Path(file_name).stem
    audio_path = audio_index.get(stem)
    if audio_path is None:
        raise RuntimeError(f"Missing WAV for eligible label stem: {stem}")

    script = _require_mapping(root.get("script"), field="script", path=label_path)
    return ReferenceClip(
        speaker_id=_require_string(
            speaker.get("speakerId"), field="speaker[0].speakerId", path=label_path
        ),
        age=age,
        province=_require_string(
            speaker.get("residenceProvince"),
            field="speaker[0].residenceProvince",
            path=label_path,
        ),
        speech_type=_require_string(
            script.get("speechType"), field="script.speechType", path=label_path
        ),
        stem=stem,
        label_path=label_path,
        audio_path=audio_path,
    )


def load_eligible_clips(label_root: Path, audio_root: Path) -> list[ReferenceClip]:
    label_paths = sorted(label_root.rglob("*.json"))
    if not label_paths:
        raise RuntimeError(f"No JSON labels found under label root: {label_root}")
    audio_index = _index_audio(audio_root)
    clips = [
        clip
        for label_path in label_paths
        if (clip := _load_reference_clip(label_path, audio_index)) is not None
    ]
    if not clips:
        raise RuntimeError("No eligible single-speaker female clips aged 50 through 69 were found.")
    return clips


def select_balanced_clips(clips: list[ReferenceClip]) -> list[ReferenceClip]:
    clips_by_speaker: dict[str, list[ReferenceClip]] = defaultdict(list)
    for clip in clips:
        clips_by_speaker[clip.speaker_id].append(clip)
    if len(clips_by_speaker) < MINIMUM_SPEAKERS:
        raise RuntimeError(
            f"At least {MINIMUM_SPEAKERS} eligible speakers are required; "
            f"received {len(clips_by_speaker)}."
        )

    selected: list[ReferenceClip] = []
    for speaker_id in sorted(clips_by_speaker):
        ranked = sorted(
            clips_by_speaker[speaker_id],
            key=lambda clip: hashlib.sha256(f"{SELECTION_SEED}:{clip.stem}".encode()).digest(),
        )
        selected.extend(ranked[:CLIPS_PER_SPEAKER])
    return selected


def _wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as wav_file:
        if wav_file.getnchannels() != 1:
            raise RuntimeError(f"Reference WAV must be mono: {path}")
        if wav_file.getsampwidth() != 2:
            raise RuntimeError(f"Reference WAV must be 16-bit PCM: {path}")
        sample_rate = wav_file.getframerate()
        if sample_rate <= 0:
            raise RuntimeError(f"Reference WAV has an invalid sample rate: {path}")
        return round(wav_file.getnframes() / sample_rate * 1_000)


def _hash_files(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.name):
        with path.open("rb") as source:
            while block := source.read(1024 * 1024):
                digest.update(block)
    return digest.hexdigest()


def _rounded_percentile(values: list[float], percentile: int) -> float:
    return round(float(np.percentile(values, percentile)), 1)


def build_reference_manifest(
    clips: list[ReferenceClip], *, generated_at: datetime
) -> dict[str, Any]:
    selected = select_balanced_clips(clips)
    per_speaker_pitch: dict[str, list[float]] = defaultdict(list)
    durations_ms: list[int] = []
    for clip in selected:
        pitch = describe_wav_pitch(clip.audio_path)
        per_speaker_pitch[clip.speaker_id].append(float(pitch["medianF0Hz"]))
        durations_ms.append(_wav_duration_ms(clip.audio_path))

    speaker_medians = [statistics.median(values) for values in per_speaker_pitch.values()]
    age_band_counts = {
        f"{decade}s": len({clip.speaker_id for clip in selected if clip.age // 10 * 10 == decade})
        for decade in sorted({clip.age // 10 * 10 for clip in selected})
    }
    label_paths = list({clip.label_path for clip in clips})
    audio_paths = [clip.audio_path for clip in selected]
    return {
        "referenceContractVersion": REFERENCE_CONTRACT_VERSION,
        "generatedAt": generated_at.astimezone(UTC).isoformat(),
        "purpose": "family-mother-candidate-acoustic-calibration",
        "prohibitedUses": [
            "speaker-identification",
            "speaker-reidentification",
            "single-speaker-voice-cloning",
        ],
        "dataset": {
            "id": DATASET_ID,
            "name": DATASET_NAME,
            "url": DATASET_URL,
            "rawDataCommitted": False,
        },
        "eligibilityContract": {
            "gender": "female",
            "minimumAgeAtRecording": TARGET_MIN_AGE,
            "maximumAgeAtRecording": TARGET_MAX_AGE,
            "singleSpeakerRecordingOnly": True,
            "minimumDistinctSpeakers": MINIMUM_SPEAKERS,
        },
        "samplingContract": {
            "method": "equal-per-speaker-stable-sha256-ranking",
            "selectionSeed": SELECTION_SEED,
            "maximumClipsPerSpeaker": CLIPS_PER_SPEAKER,
        },
        "coverage": {
            "eligibleSpeakers": len({clip.speaker_id for clip in clips}),
            "selectedSpeakers": len(per_speaker_pitch),
            "selectedClips": len(selected),
            "speakerCountByAgeBand": age_band_counts,
            "provinceCodes": sorted({clip.province for clip in selected}),
            "speechTypes": sorted({clip.speech_type for clip in selected}),
        },
        "acousticReference": {
            "aggregationUnit": "per-speaker-median-of-selected-clip-medians",
            "pitchAlgorithm": "praat-autocorrelation",
            "speakerMedianF0Hz": {
                "p25": _rounded_percentile(speaker_medians, 25),
                "median": _rounded_percentile(speaker_medians, 50),
                "p75": _rounded_percentile(speaker_medians, 75),
            },
            "selectedClipDurationMs": {
                "p25": round(float(np.percentile(durations_ms, 25))),
                "median": round(float(np.percentile(durations_ms, 50))),
                "p75": round(float(np.percentile(durations_ms, 75))),
            },
        },
        "sourceIntegrity": {
            "eligibleLabelContentSha256": _hash_files(label_paths),
            "selectedAudioContentSha256": _hash_files(audio_paths),
        },
        "privacy": {
            "containsSpeakerIdentifiers": False,
            "containsSourceFileNames": False,
            "containsTranscripts": False,
            "containsAudio": False,
            "statisticsAreAggregateOnly": True,
        },
    }


def write_reference_manifest(output: Path, manifest: dict[str, Any]) -> None:
    if output.exists():
        raise RuntimeError(f"Output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    clips = load_eligible_clips(args.label_root.resolve(), args.audio_root.resolve())
    manifest = build_reference_manifest(clips, generated_at=datetime.now(UTC))
    write_reference_manifest(args.output.resolve(), manifest)
    print(
        "reference "
        f"speakers={manifest['coverage']['selectedSpeakers']} "
        f"clips={manifest['coverage']['selectedClips']} "
        f"output={args.output.resolve()}",
        flush=True,
    )


if __name__ == "__main__":
    main()
