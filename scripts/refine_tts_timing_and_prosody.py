from __future__ import annotations

import argparse
import hashlib
import tempfile
from pathlib import Path

import numpy as np
import parselmouth
import soundfile as sf
from parselmouth.praat import call

from scripts.normalize_tts_pitch_register import (
    load_manifest_artifact,
    normalize_pitch_register,
)
from scripts.tts_audition_common import (
    describe_wav,
    describe_wav_pitch,
    prepare_output_directory,
    write_manifest,
)

DEFAULT_PAUSE_SCALE = 0.65
DEFAULT_PROSODY_SCALE = 0.8
LINGUISTIC_PAUSE_MINIMUM_SECONDS = 0.12


def compress_pitch_excursions(
    source_path: Path,
    output_path: Path,
    *,
    center_f0_hz: float,
    prosody_scale: float,
) -> None:
    if center_f0_hz <= 0:
        raise ValueError("Pitch center must be positive.")
    if not 0 < prosody_scale <= 1:
        raise ValueError("Prosody scale must be greater than zero and at most one.")
    source = parselmouth.Sound(str(source_path))
    manipulation = call(source, "To Manipulation", 0.01, 65.0, 400.0)
    pitch_tier = call(manipulation, "Extract pitch tier")
    formula = f"{center_f0_hz} * exp({prosody_scale} * ln(self / {center_f0_hz}))"
    call(pitch_tier, "Formula", formula)
    call([pitch_tier, manipulation], "Replace pitch tier")
    refined = call(manipulation, "Get resynthesis (overlap-add)")
    refined.save(str(output_path), "WAV")


def _two_cluster_intensity_threshold(values: np.ndarray) -> float:
    centers = np.array([float(values.min()), float(values.max())])
    for _ in range(100):
        assignments = np.abs(values[:, np.newaxis] - centers).argmin(axis=1)
        updated = np.array([float(values[assignments == index].mean()) for index in range(2)])
        if np.allclose(updated, centers):
            break
        centers = updated
    return float(centers.mean())


def detect_linguistic_pauses(
    source_path: Path,
    *,
    minimum_duration_seconds: float = LINGUISTIC_PAUSE_MINIMUM_SECONDS,
) -> list[tuple[float, float]]:
    sound = parselmouth.Sound(str(source_path))
    intensity = sound.to_intensity(
        minimum_pitch=75.0,
        time_step=0.01,
        subtract_mean=True,
    )
    values = intensity.values[0]
    threshold = _two_cluster_intensity_threshold(values)
    below_threshold = values < threshold
    starts = np.flatnonzero(below_threshold & ~np.r_[False, below_threshold[:-1]])
    ends = np.flatnonzero(below_threshold & ~np.r_[below_threshold[1:], False])
    times = intensity.xs()
    half_step = intensity.dx / 2
    pauses = []
    for start, end in zip(starts, ends, strict=True):
        start_time = max(0.0, float(times[start] - half_step))
        end_time = min(sound.duration, float(times[end] + half_step))
        if end_time - start_time >= minimum_duration_seconds:
            pauses.append((start_time, end_time))
    return pauses


def compress_linguistic_pauses(
    source_path: Path,
    output_path: Path,
    *,
    pause_scale: float,
) -> list[dict[str, float]]:
    if not 0 < pause_scale <= 1:
        raise ValueError("Pause scale must be greater than zero and at most one.")
    audio, sample_rate = sf.read(source_path, dtype="float32", always_2d=True)
    pauses = detect_linguistic_pauses(source_path)
    cursor = 0
    chunks = []
    changes = []
    for start_time, end_time in pauses:
        start = round(start_time * sample_rate)
        end = round(end_time * sample_rate)
        original_samples = end - start
        retained_samples = round(original_samples * pause_scale)
        retained_left = retained_samples // 2
        retained_right = retained_samples - retained_left
        left_end = start + retained_left
        right_start = end - retained_right
        chunks.append(audio[cursor:left_end])
        cursor = right_start
        changes.append(
            {
                "startSeconds": round(start_time, 3),
                "endSeconds": round(end_time, 3),
                "originalDurationSeconds": round(original_samples / sample_rate, 3),
                "refinedDurationSeconds": round(retained_samples / sample_rate, 3),
            }
        )
    chunks.append(audio[cursor:])
    refined = np.concatenate(chunks, axis=0)
    sf.write(output_path, refined, sample_rate, format="WAV", subtype="PCM_16")
    return changes


def refine_timing_and_prosody(
    source_path: Path,
    output_path: Path,
    *,
    center_f0_hz: float,
    prosody_scale: float,
    pause_scale: float,
) -> list[dict[str, float]]:
    with tempfile.TemporaryDirectory(prefix="maeum-call-tts-refinement-") as temp_dir:
        temp_root = Path(temp_dir)
        pitch_refined_path = temp_root / "pitch-refined.wav"
        timing_refined_path = temp_root / "timing-refined.wav"
        compress_pitch_excursions(
            source_path,
            pitch_refined_path,
            center_f0_hz=center_f0_hz,
            prosody_scale=prosody_scale,
        )
        pause_changes = compress_linguistic_pauses(
            pitch_refined_path,
            timing_refined_path,
            pause_scale=pause_scale,
        )
        timing_pitch = describe_wav_pitch(timing_refined_path)
        normalize_pitch_register(
            timing_refined_path,
            output_path,
            source_median_f0_hz=float(timing_pitch["medianF0Hz"]),
            target_median_f0_hz=center_f0_hz,
        )
    return pause_changes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Shorten measured linguistic pauses and reduce relative pitch excursions without "
            "changing the established pitch register."
        )
    )
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--source-voice", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pause-scale", type=float, default=DEFAULT_PAUSE_SCALE)
    parser.add_argument("--prosody-scale", type=float, default=DEFAULT_PROSODY_SCALE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = prepare_output_directory(args.output_dir)
    source_manifest_path = args.source_manifest.resolve()
    source_artifact, source_path = load_manifest_artifact(source_manifest_path, args.source_voice)
    center_f0_hz = float(source_artifact["pitchAnalysis"]["medianF0Hz"])
    output_path = output_dir / f"01_{args.source_voice}_timing_prosody_refined.wav"
    pause_changes = refine_timing_and_prosody(
        source_path,
        output_path,
        center_f0_hz=center_f0_hz,
        prosody_scale=args.prosody_scale,
        pause_scale=args.pause_scale,
    )
    artifact = describe_wav(
        output_path,
        position=1,
        voice=f"{args.source_voice}_timing_prosody_refined",
        description=(
            "Long linguistic pauses shortened while voiced durations, formants, pitch center, "
            "and user-directed contour directions remain unchanged."
        ),
    )
    artifact["pitchAnalysis"] = describe_wav_pitch(output_path)
    artifact["sourceSha256"] = source_artifact["sha256"]
    manifest = {
        "roleId": "family_mother",
        "selectionStatus": "awaiting-user-selection",
        "transformation": "timing-and-relative-prosody-refinement",
        "sourceManifestSha256": hashlib.sha256(source_manifest_path.read_bytes()).hexdigest(),
        "sourceVoice": args.source_voice,
        "pitchCenterF0Hz": center_f0_hz,
        "prosodyScale": args.prosody_scale,
        "pauseScale": args.pause_scale,
        "pauseDetection": {
            "algorithm": "two-cluster-praat-intensity",
            "linguisticPauseMinimumSeconds": LINGUISTIC_PAUSE_MINIMUM_SECONDS,
        },
        "pauseChanges": pause_changes,
        "relativeContourDirectionsPreserved": True,
        "voicedDurationsChanged": False,
        "formantsShifted": False,
        "artifacts": [artifact],
    }
    manifest_path = write_manifest(output_dir, manifest)
    print(f"manifest {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
