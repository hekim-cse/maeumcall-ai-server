from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from scripts.tts_audition_common import (
    DEFAULT_AUDITION_TEXT,
    describe_wav,
    prepare_output_directory,
    seed_local_inference,
    write_manifest,
)
from services.tts.catalog import TTS_VOICE_CATALOG
from services.tts.qwen_provider import QwenTTSProvider

DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
DEFAULT_REVISION = "85e237c12c027371202489a0ec509ded67b5e4b5"
DEFAULT_MAX_NEW_TOKENS = 1_200
DEFAULT_SEED = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the same Korean audition sentence with every verified Qwen3-TTS voice."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), required=True)
    parser.add_argument(
        "--dtype",
        choices=("float32", "float16", "bfloat16"),
        required=True,
    )
    parser.add_argument("--text", default=DEFAULT_AUDITION_TEXT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--max-new-tokens", type=int, default=DEFAULT_MAX_NEW_TOKENS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow downloading the exact requested revision when it is not cached.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = prepare_output_directory(args.output_dir)
    seed_local_inference(args.seed)

    provider = QwenTTSProvider(
        model_name=args.model,
        model_revision=args.revision,
        local_files_only=not args.allow_network,
        device=args.device,
        dtype=args.dtype,
        max_new_tokens=args.max_new_tokens,
    )
    provider.probe()

    artifacts: list[dict[str, str | int | bool]] = []
    for position, profile in enumerate(TTS_VOICE_CATALOG, start=1):
        result = provider.synthesize(text=args.text, voice=profile.id)
        filename = f"{position:02d}_{profile.id.value}.wav"
        output_path = output_dir / filename
        output_path.write_bytes(result.audio)
        artifact = describe_wav(
            output_path,
            position=position,
            voice=profile.id.value,
            description=profile.description,
        )
        artifact["nativeLanguage"] = profile.nativeLanguage
        artifact["nativeKorean"] = profile.nativeKorean
        artifacts.append(artifact)
        print(f"generated {filename}", flush=True)

    manifest = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "provider": provider.provider_name,
        "model": args.model,
        "modelRevision": args.revision,
        "language": "Korean",
        "device": args.device,
        "dtype": args.dtype,
        "text": args.text,
        "maxNewTokens": args.max_new_tokens,
        "seed": args.seed,
        "artifacts": artifacts,
    }
    manifest_path = write_manifest(output_dir, manifest)
    print(f"manifest {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
