from __future__ import annotations

import argparse
import importlib.metadata
from datetime import UTC, datetime
from pathlib import Path

from scripts.tts_audition_common import (
    DEFAULT_AUDITION_TEXT,
    describe_wav,
    prepare_output_directory,
    seed_local_inference,
    write_manifest,
)

MODEL_ID = "ResembleAI/chatterbox"
MODEL_REVISION = "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
T3_MODEL = "t3_mtl23ls_v3.safetensors"
RUNTIME_VERSION = "0.1.7"
RUNTIME_SOURCE_REVISION = "5de7a54aa4e5e2baadb0182dde554908b48b85c2"
DEFAULT_SEED = 42
MODEL_FILES = (
    "Cangjie5_TC.json",
    "conds.pt",
    "grapheme_mtl_merged_expanded_v1.json",
    "s3gen.pt",
    T3_MODEL,
    "ve.pt",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the built-in Korean Chatterbox Multilingual V3 voice "
            "in an isolated local runtime."
        )
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), required=True)
    parser.add_argument("--text", default=DEFAULT_AUDITION_TEXT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--exaggeration", type=float, default=0.5)
    parser.add_argument("--cfg-weight", type=float, default=0.5)
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Acknowledge the revision check and exact model download from Hugging Face.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.allow_network:
        raise RuntimeError("Chatterbox audition requires explicit --allow-network.")
    output_dir = prepare_output_directory(args.output_dir)

    installed_version = importlib.metadata.version("chatterbox-tts")
    if installed_version != RUNTIME_VERSION:
        raise RuntimeError(
            f"Chatterbox runtime version mismatch: expected {RUNTIME_VERSION}, "
            f"received {installed_version}"
        )

    from huggingface_hub import HfApi, snapshot_download

    seed_local_inference(args.seed)
    current_revision = HfApi().model_info(MODEL_ID).sha
    if current_revision != MODEL_REVISION:
        raise RuntimeError(
            f"Chatterbox model revision changed: expected {MODEL_REVISION}, "
            f"received {current_revision}"
        )
    model_dir = Path(
        snapshot_download(
            repo_id=MODEL_ID,
            revision=MODEL_REVISION,
            allow_patterns=MODEL_FILES,
        )
    )

    import librosa
    import torchaudio
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    model = ChatterboxMultilingualTTS.from_local(
        model_dir,
        device=args.device,
        t3_model=T3_MODEL,
    )
    audio = model.generate(
        args.text,
        language_id="ko",
        exaggeration=args.exaggeration,
        cfg_weight=args.cfg_weight,
    )
    output_path = output_dir / "01_builtin.wav"
    torchaudio.save(
        str(output_path),
        audio.cpu(),
        model.sr,
        encoding="PCM_S",
        bits_per_sample=16,
    )
    saved_audio, saved_sample_rate = librosa.load(output_path, sr=None)
    watermark_score = float(
        model.watermarker.get_watermark(saved_audio, saved_sample_rate).item()
    )
    if watermark_score < 0.5:
        raise RuntimeError(
            f"Chatterbox output watermark was not detected: {watermark_score}"
        )
    artifact = describe_wav(
        output_path,
        position=1,
        voice="builtin",
        description="Chatterbox Multilingual V3 내장 기준 음성",
    )
    print(f"generated {output_path.name}", flush=True)

    manifest = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "provider": "chatterbox-multilingual-v3",
        "executionMode": "local-isolated-evaluation",
        "model": MODEL_ID,
        "modelRevision": MODEL_REVISION,
        "modelFiles": list(MODEL_FILES),
        "t3Model": T3_MODEL,
        "runtimeVersion": installed_version,
        "runtimeSourceRevision": RUNTIME_SOURCE_REVISION,
        "language": "Korean",
        "languageId": "ko",
        "device": args.device,
        "text": args.text,
        "seed": args.seed,
        "exaggeration": args.exaggeration,
        "cfgWeight": args.cfg_weight,
        "voiceSource": "model-builtin-conditionals",
        "watermark": {"type": "PerTh", "detected": True, "score": watermark_score},
        "artifacts": [artifact],
    }
    manifest_path = write_manifest(output_dir, manifest)
    print(f"manifest {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
