from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from services.tts.catalog import TTS_VOICE_CATALOG
from services.tts.qwen_provider import QwenTTSProvider

DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
DEFAULT_REVISION = "85e237c12c027371202489a0ec509ded67b5e4b5"
DEFAULT_TEXT = "안녕하세요. 마음콜 통화 연습을 시작하겠습니다. 천천히 말씀해 주세요."
DEFAULT_MAX_NEW_TOKENS = 1_200


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
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--max-new-tokens", type=int, default=DEFAULT_MAX_NEW_TOKENS)
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow downloading the exact requested revision when it is not cached.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir: Path = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    existing_outputs = sorted(output_dir.glob("*.wav"))
    if existing_outputs:
        raise RuntimeError(f"Output directory already contains WAV files: {output_dir}")

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
        artifacts.append(
            {
                "position": position,
                "voice": profile.id.value,
                "description": profile.description,
                "nativeLanguage": profile.nativeLanguage,
                "nativeKorean": profile.nativeKorean,
                "filename": filename,
                "sampleRate": result.sample_rate,
                "sha256": hashlib.sha256(result.audio).hexdigest(),
            }
        )
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
        "artifacts": artifacts,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"manifest {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
