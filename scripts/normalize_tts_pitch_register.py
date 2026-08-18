from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import parselmouth
from parselmouth.praat import call

from scripts.tts_audition_common import (
    describe_wav,
    describe_wav_pitch,
    prepare_output_directory,
    write_manifest,
)


def load_manifest_artifact(manifest_path: Path, voice: str) -> tuple[dict, Path]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    matches = [artifact for artifact in manifest["artifacts"] if artifact["voice"] == voice]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one artifact for voice '{voice}'.")
    artifact = matches[0]
    audio_path = manifest_path.parent / artifact["filename"]
    actual_sha256 = hashlib.sha256(audio_path.read_bytes()).hexdigest()
    if actual_sha256 != artifact["sha256"]:
        raise RuntimeError(f"Artifact hash mismatch: {audio_path}")
    return artifact, audio_path


def normalize_pitch_register(
    source_path: Path,
    output_path: Path,
    *,
    source_median_f0_hz: float,
    target_median_f0_hz: float,
) -> float:
    if source_median_f0_hz <= 0 or target_median_f0_hz <= 0:
        raise ValueError("Pitch medians must be positive.")
    scale = target_median_f0_hz / source_median_f0_hz
    source = parselmouth.Sound(str(source_path))
    manipulation = call(source, "To Manipulation", 0.01, 65.0, 400.0)
    pitch_tier = call(manipulation, "Extract pitch tier")
    call(pitch_tier, "Multiply frequencies", source.xmin, source.xmax, scale)
    call([pitch_tier, manipulation], "Replace pitch tier")
    normalized = call(manipulation, "Get resynthesis (overlap-add)")
    normalized.save(str(output_path), "WAV")
    return scale


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Preserve a generated utterance's relative prosody while restoring the absolute "
            "pitch register from a versioned reference artifact."
        )
    )
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--source-voice", required=True)
    parser.add_argument("--reference-manifest", type=Path, required=True)
    parser.add_argument("--reference-voice", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = prepare_output_directory(args.output_dir)
    source_manifest_path = args.source_manifest.resolve()
    reference_manifest_path = args.reference_manifest.resolve()
    source_artifact, source_path = load_manifest_artifact(source_manifest_path, args.source_voice)
    reference_artifact, _ = load_manifest_artifact(reference_manifest_path, args.reference_voice)
    source_median = float(source_artifact["pitchAnalysis"]["medianF0Hz"])
    target_median = float(reference_artifact["pitchAnalysis"]["medianF0Hz"])
    output_path = output_dir / f"01_{args.source_voice}_register_preserved.wav"
    scale = normalize_pitch_register(
        source_path,
        output_path,
        source_median_f0_hz=source_median,
        target_median_f0_hz=target_median,
    )
    artifact = describe_wav(
        output_path,
        position=1,
        voice=f"{args.source_voice}_register_preserved",
        description=(
            "Relative prosody preserved from the source artifact; absolute pitch register "
            "restored from the approved parent candidate."
        ),
    )
    artifact["pitchAnalysis"] = describe_wav_pitch(output_path)
    artifact["sourceSha256"] = source_artifact["sha256"]
    artifact["registerReferenceSha256"] = reference_artifact["sha256"]
    manifest = {
        "roleId": "family_mother",
        "selectionStatus": "awaiting-user-selection",
        "transformation": "reference-register-preserving-prosody-resynthesis",
        "algorithm": "praat-overlap-add-pitch-tier-scaling",
        "sourceManifestSha256": hashlib.sha256(source_manifest_path.read_bytes()).hexdigest(),
        "referenceManifestSha256": hashlib.sha256(reference_manifest_path.read_bytes()).hexdigest(),
        "sourceVoice": args.source_voice,
        "registerReferenceVoice": args.reference_voice,
        "sourceMedianF0Hz": source_median,
        "targetMedianF0Hz": target_median,
        "pitchScale": round(scale, 6),
        "relativeProsodyPreserved": True,
        "formantsShifted": False,
        "artifacts": [artifact],
    }
    manifest_path = write_manifest(output_dir, manifest)
    print(f"manifest {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
