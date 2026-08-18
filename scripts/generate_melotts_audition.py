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

MODEL_ID = "myshell-ai/MeloTTS-Korean"
MODEL_REVISION = "0207e5adfc90129a51b6b03d89be6d84360ed323"
BERT_MODEL_ID = "kykim/bert-kor-base"
BERT_MODEL_REVISION = "1779cc0982ada0216dd6de0dd4e86fb78201926d"
MELOTTS_VERSION = "0.1.2"
MELOTTS_SOURCE_REVISION = "209145371cff8fc3bd60d7be902ea69cbdb7965a"
DEFAULT_SEED = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the Korean MeloTTS reference audition in an isolated runtime."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), required=True)
    parser.add_argument("--text", default=DEFAULT_AUDITION_TEXT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Acknowledge the revision checks and model downloads made against Hugging Face.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.allow_network:
        raise RuntimeError("MeloTTS audition requires explicit --allow-network.")
    output_dir = prepare_output_directory(args.output_dir)

    installed_version = importlib.metadata.version("melotts")
    if installed_version != MELOTTS_VERSION:
        raise RuntimeError(
            f"MeloTTS runtime version mismatch: expected {MELOTTS_VERSION}, "
            f"received {installed_version}"
        )

    from huggingface_hub import HfApi, snapshot_download

    seed_local_inference(args.seed)

    current_bert_revision = HfApi().model_info(BERT_MODEL_ID).sha
    if current_bert_revision != BERT_MODEL_REVISION:
        raise RuntimeError(
            f"MeloTTS BERT revision changed: expected {BERT_MODEL_REVISION}, "
            f"received {current_bert_revision}"
        )
    snapshot_download(
        repo_id=BERT_MODEL_ID,
        revision=BERT_MODEL_REVISION,
    )

    model_dir = Path(
        snapshot_download(
            repo_id=MODEL_ID,
            revision=MODEL_REVISION,
            allow_patterns=("checkpoint.pth", "config.json"),
        )
    )

    from melo.api import TTS

    model = TTS(
        language="KR",
        device=args.device,
        use_hf=False,
        config_path=str(model_dir / "config.json"),
        ckpt_path=str(model_dir / "checkpoint.pth"),
    )
    speaker_id = model.hps.data.spk2id["KR"]
    output_path = output_dir / "01_kr.wav"
    model.tts_to_file(
        args.text,
        speaker_id,
        str(output_path),
        speed=args.speed,
        quiet=True,
    )
    artifact = describe_wav(
        output_path,
        position=1,
        voice="kr",
        description="MeloTTS 한국어 단일 고정 음성",
    )
    print(f"generated {output_path.name}", flush=True)

    manifest = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "provider": "melotts",
        "executionMode": "local-isolated-evaluation",
        "model": MODEL_ID,
        "modelRevision": MODEL_REVISION,
        "bertModel": BERT_MODEL_ID,
        "bertModelRevision": BERT_MODEL_REVISION,
        "runtimeVersion": installed_version,
        "runtimeSourceRevision": MELOTTS_SOURCE_REVISION,
        "language": "Korean",
        "device": args.device,
        "text": args.text,
        "seed": args.seed,
        "speed": args.speed,
        "artifacts": [artifact],
    }
    manifest_path = write_manifest(output_dir, manifest)
    print(f"manifest {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
