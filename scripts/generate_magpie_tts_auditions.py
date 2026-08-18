from __future__ import annotations

import argparse
import shutil
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.tts_audition_common import (
    DEFAULT_AUDITION_TEXT,
    describe_wav,
    prepare_output_directory,
    write_manifest,
)

MODEL_ID = "nvidia/magpie_tts_multilingual_357m"
MODEL_REVISION = "452ef560f972c38d5fc16476259aac9456453547"
MODEL_VERSION = "v2607"
SPACE_ID = "nvidia/magpie_tts_multilingual_demo"
SPACE_REVISION = "9010af92ce9989343a952f5fd6e4b9e1f4cff9b5"
SPEAKERS = (
    ("Aria", "NVIDIA 고정 여성 음성 Aria"),
    ("Jason", "NVIDIA 고정 남성 음성 Jason"),
    ("John", "NVIDIA 고정 남성 음성 John"),
    ("Leo", "NVIDIA 고정 남성 음성 Leo"),
    ("Sofia", "NVIDIA 고정 여성 음성 Sofia"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one Korean audition sentence with the five MagpieTTS v2607 voices."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--text", default=DEFAULT_AUDITION_TEXT)
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Acknowledge that the official NVIDIA Hugging Face Space will receive the text.",
    )
    return parser.parse_args()


def assert_remote_revisions() -> None:
    from huggingface_hub import HfApi

    api = HfApi()
    current_model_revision = api.model_info(MODEL_ID).sha
    if current_model_revision != MODEL_REVISION:
        raise RuntimeError(
            f"Magpie model revision changed: expected {MODEL_REVISION}, "
            f"received {current_model_revision}"
        )
    current_space_revision = api.space_info(SPACE_ID).sha
    if current_space_revision != SPACE_REVISION:
        raise RuntimeError(
            f"Magpie Space revision changed: expected {SPACE_REVISION}, "
            f"received {current_space_revision}"
        )


def main() -> None:
    args = parse_args()
    if not args.allow_network:
        raise RuntimeError("Magpie hosted audition requires explicit --allow-network.")

    output_dir = prepare_output_directory(args.output_dir)
    assert_remote_revisions()

    from gradio_client import Client
    from huggingface_hub import get_token

    artifacts: list[dict[str, str | int]] = []
    with TemporaryDirectory(prefix="maeum-call-magpie-download-") as download_dir:
        client = Client(
            SPACE_ID,
            token=get_token(),
            verbose=False,
            download_files=download_dir,
        )
        for position, (speaker, description) in enumerate(SPEAKERS, start=1):
            downloaded_path = client.predict(
                args.text,
                "Korean",
                speaker,
                "Apply TN",
                api_name="/demo_tts",
            )
            output_path = output_dir / f"{position:02d}_{speaker.lower()}.wav"
            shutil.copyfile(Path(downloaded_path), output_path)
            artifacts.append(
                describe_wav(
                    output_path,
                    position=position,
                    voice=speaker.lower(),
                    description=description,
                )
            )
            print(f"generated {output_path.name}", flush=True)

    manifest = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "provider": "nvidia-magpie-official-space",
        "executionMode": "hosted-evaluation-only",
        "model": MODEL_ID,
        "modelVersion": MODEL_VERSION,
        "modelRevision": MODEL_REVISION,
        "space": SPACE_ID,
        "spaceRevision": SPACE_REVISION,
        "language": "Korean",
        "text": args.text,
        "textNormalization": True,
        "artifacts": artifacts,
    }
    manifest_path = write_manifest(output_dir, manifest)
    print(f"manifest {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
