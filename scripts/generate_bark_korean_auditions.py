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

MODEL_ID = "suno/bark-small"
MODEL_REVISION = "1dbd7a128513b8ae4a4e2130fed57b7ac9da5bcd"
TRANSFORMERS_VERSION = "4.57.3"
TORCH_VERSION = "2.8.0"
DEFAULT_SEED = 42
KOREAN_VOICE_PRESETS = tuple(f"v2/ko_speaker_{index}" for index in range(10))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the same Korean audition sentence with all ten official "
            "Bark Small Korean V2 speaker presets."
        )
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), required=True)
    parser.add_argument("--text", default=DEFAULT_AUDITION_TEXT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Acknowledge the revision check and exact model download from Hugging Face.",
    )
    return parser.parse_args()


def _preset_files(preset: str) -> tuple[str, ...]:
    return tuple(
        f"speaker_embeddings/{preset}_{component}_prompt.npy"
        for component in ("semantic", "coarse", "fine")
    )


def main() -> None:
    args = parse_args()
    if not args.allow_network:
        raise RuntimeError("Bark audition requires explicit --allow-network.")
    output_dir = prepare_output_directory(args.output_dir)

    transformers_version = importlib.metadata.version("transformers")
    torch_version = importlib.metadata.version("torch")
    if transformers_version != TRANSFORMERS_VERSION:
        raise RuntimeError(
            f"Transformers version mismatch: expected {TRANSFORMERS_VERSION}, "
            f"received {transformers_version}"
        )
    if torch_version != TORCH_VERSION:
        raise RuntimeError(
            f"Torch version mismatch: expected {TORCH_VERSION}, received {torch_version}"
        )

    from huggingface_hub import HfApi, hf_hub_download

    model_info = HfApi().model_info(MODEL_ID)
    if model_info.sha != MODEL_REVISION:
        raise RuntimeError(
            f"Bark Small revision changed: expected {MODEL_REVISION}, received {model_info.sha}"
        )
    available_files = {sibling.rfilename for sibling in model_info.siblings}
    required_preset_files = {
        filename for preset in KOREAN_VOICE_PRESETS for filename in _preset_files(preset)
    }
    missing_files = sorted(required_preset_files - available_files)
    if missing_files:
        raise RuntimeError(f"Bark Korean preset files are missing: {missing_files}")

    import numpy as np
    import torch
    import torchaudio
    from transformers import AutoProcessor, BarkModel

    if args.device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("Bark audition requested MPS, but MPS is not available.")

    processor = AutoProcessor.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
    )
    model = BarkModel.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
        dtype=torch.float32,
    ).to(args.device)
    model.eval()

    artifacts: list[dict[str, str | int]] = []
    for position, preset in enumerate(KOREAN_VOICE_PRESETS, start=1):
        voice_seed = args.seed + position - 1
        seed_local_inference(voice_seed)
        history_prompt = {
            prompt_key: np.load(
                hf_hub_download(
                    repo_id=MODEL_ID,
                    filename=f"speaker_embeddings/{preset}_{prompt_key}.npy",
                    revision=MODEL_REVISION,
                )
            )
            for prompt_key in ("semantic_prompt", "coarse_prompt", "fine_prompt")
        }
        inputs = processor(
            args.text,
            voice_preset=history_prompt,
            return_tensors="pt",
        ).to(args.device)
        with torch.inference_mode():
            audio = model.generate(**inputs)
        if audio.ndim == 1:
            audio = audio.unsqueeze(0)

        voice_id = preset.rsplit("/", maxsplit=1)[-1]
        output_path = output_dir / f"{position:02d}_{voice_id}.wav"
        torchaudio.save(
            str(output_path),
            audio.cpu(),
            model.generation_config.sample_rate,
            encoding="PCM_S",
            bits_per_sample=16,
        )
        artifact = describe_wav(
            output_path,
            position=position,
            voice=voice_id,
            description=f"Bark Small 한국어 V2 공식 프리셋 {position - 1}",
        )
        artifact["preset"] = preset
        artifact["seed"] = voice_seed
        artifacts.append(artifact)
        print(f"generated {output_path.name}", flush=True)

    manifest = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "provider": "bark-small",
        "executionMode": "local-evaluation",
        "model": MODEL_ID,
        "modelRevision": MODEL_REVISION,
        "runtime": {
            "transformers": transformers_version,
            "torch": torch_version,
        },
        "language": "Korean",
        "device": args.device,
        "text": args.text,
        "baseSeed": args.seed,
        "seedStrategy": "base-seed-plus-zero-based-position",
        "voicePresets": list(KOREAN_VOICE_PRESETS),
        "artifacts": artifacts,
    }
    manifest_path = write_manifest(output_dir, manifest)
    print(f"manifest {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
