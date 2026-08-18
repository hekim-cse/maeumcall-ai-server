from __future__ import annotations

import hashlib
import json
import random
import wave
from pathlib import Path
from typing import Any

DEFAULT_AUDITION_TEXT = (
    "안녕하세요. 마음콜 통화 연습을 시작하겠습니다. 천천히 말씀해 주세요."
)


def seed_local_inference(seed: int) -> None:
    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def prepare_output_directory(output_dir: Path) -> Path:
    resolved = output_dir.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    existing_entries = sorted(path.name for path in resolved.iterdir())
    if existing_entries:
        raise RuntimeError(
            f"Output directory must be empty: {resolved} ({', '.join(existing_entries)})"
        )
    return resolved


def describe_wav(
    path: Path,
    *,
    position: int,
    voice: str,
    description: str,
) -> dict[str, str | int]:
    with wave.open(str(path), "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()

    return {
        "position": position,
        "voice": voice,
        "description": description,
        "filename": path.name,
        "sampleRate": sample_rate,
        "channels": channels,
        "bitDepth": sample_width * 8,
        "durationMs": round(frame_count / sample_rate * 1_000),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def write_manifest(output_dir: Path, manifest: dict[str, Any]) -> Path:
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path
