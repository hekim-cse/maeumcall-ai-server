from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any

from scripts.tts_audition_common import (
    describe_wav,
    describe_wav_pitch,
    prepare_output_directory,
    seed_local_inference,
    write_manifest,
)

MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
MODEL_REVISION = "fd4b254389122332181a7c3db7f27e918eec64e3"
QWEN_TTS_VERSION = "0.1.1"
CAST_VERSION = 2
ROLE_ID = "family_mother"
VOICE_ID = "reference_warm_everyday_mature_age_restrained_prosody"
DEFAULT_SEED = 42
DEFAULT_MAX_NEW_TOKENS = 1_200
DEFAULT_AUDITION_TEXT = "그래, 오늘도 수고 많았어. 무슨 일이 있었는지 엄마한테 천천히 말해 봐."


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_reference_artifact(
    manifest_path: Path,
    *,
    voice_id: str,
) -> tuple[dict[str, Any], Path, str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("selectionStatus") != "approved-by-user":
        raise RuntimeError("Voice clone reference must be approved by the user.")
    matches = [
        artifact for artifact in manifest.get("artifacts", []) if artifact.get("voice") == voice_id
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one approved artifact for voice '{voice_id}'.")
    artifact = matches[0]
    reference_path = manifest_path.parent / artifact["filename"]
    if not reference_path.is_file():
        raise RuntimeError(f"Voice clone reference WAV is missing: {reference_path}")
    actual_sha256 = sha256_file(reference_path)
    if actual_sha256 != artifact.get("sha256"):
        raise RuntimeError("Voice clone reference WAV hash does not match its manifest.")
    reference_text = manifest.get("text")
    if not isinstance(reference_text, str) or not reference_text.strip():
        raise RuntimeError("Voice clone ICL mode requires the exact reference transcript.")
    return artifact, reference_path, reference_text.strip()


def resolve_model_snapshot(*, allow_network: bool) -> str:
    try:
        from huggingface_hub import model_info, snapshot_download
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Voice clone generation requires the packages in requirements-tts.txt."
        ) from exc
    if allow_network:
        info = model_info(MODEL_ID, revision=MODEL_REVISION)
        if info.sha != MODEL_REVISION:
            raise RuntimeError(
                f"Pinned Base model revision mismatch: expected {MODEL_REVISION}, received {info.sha}"
            )
    return snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_files_only=not allow_network,
    )


def _validate_device(*, torch: Any, device: str, dtype: str) -> None:
    if device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("Qwen Voice Clone requested MPS, but MPS is not available.")
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("Qwen Voice Clone requested CUDA, but CUDA is not available.")
    if device == "cpu" and dtype != "float32":
        raise RuntimeError("Qwen Voice Clone CPU execution requires float32.")


def save_voice_clone_prompt(
    prompt_item: Any,
    output_path: Path,
    *,
    reference_text: str,
    reference_sha256: str,
) -> dict[str, Any]:
    from safetensors.torch import save_file

    if prompt_item.x_vector_only_mode or not prompt_item.icl_mode:
        raise RuntimeError("The production mother voice requires a full ICL clone prompt.")
    if prompt_item.ref_code is None:
        raise RuntimeError("The ICL clone prompt is missing reference speech codes.")
    tensors = {
        "ref_code": prompt_item.ref_code.detach().cpu().contiguous(),
        "ref_spk_embedding": prompt_item.ref_spk_embedding.detach().cpu().contiguous(),
    }
    metadata = {
        "schemaVersion": "1",
        "castVersion": str(CAST_VERSION),
        "roleId": ROLE_ID,
        "voiceId": VOICE_ID,
        "model": MODEL_ID,
        "modelRevision": MODEL_REVISION,
        "referenceSha256": reference_sha256,
        "referenceText": reference_text,
        "xVectorOnlyMode": "false",
        "iclMode": "true",
    }
    save_file(tensors, str(output_path), metadata=metadata)
    return {
        "filename": output_path.name,
        "format": "safetensors",
        "sha256": sha256_file(output_path),
        "xVectorOnlyMode": False,
        "iclMode": True,
        "tensorShapes": {name: list(tensor.shape) for name, tensor in tensors.items()},
        "tensorDtypes": {name: str(tensor.dtype) for name, tensor in tensors.items()},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build and validate the reusable Qwen Base ICL prompt for the approved family-mother "
            "voice, then synthesize one fixed validation line."
        )
    )
    parser.add_argument("--reference-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), required=True)
    parser.add_argument(
        "--dtype",
        choices=("float32", "float16", "bfloat16"),
        required=True,
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--max-new-tokens", type=int, default=DEFAULT_MAX_NEW_TOKENS)
    parser.add_argument("--audition-text", default=DEFAULT_AUDITION_TEXT)
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow checking and downloading the exact pinned Base model revision.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audition_text = args.audition_text.strip()
    if not audition_text:
        raise RuntimeError("Voice clone validation text must not be blank.")
    output_dir = prepare_output_directory(args.output_dir)
    reference_manifest_path = args.reference_manifest.resolve()
    reference_artifact, reference_path, reference_text = load_reference_artifact(
        reference_manifest_path,
        voice_id=VOICE_ID,
    )

    runtime_version = importlib.metadata.version("qwen-tts")
    if runtime_version != QWEN_TTS_VERSION:
        raise RuntimeError(
            f"qwen-tts version mismatch: expected {QWEN_TTS_VERSION}, received {runtime_version}"
        )
    model_path = resolve_model_snapshot(allow_network=args.allow_network)

    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel

    _validate_device(torch=torch, device=args.device, dtype=args.dtype)
    torch_dtype = {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
    }[args.dtype]
    model = Qwen3TTSModel.from_pretrained(
        model_path,
        device_map=args.device,
        dtype=torch_dtype,
        attn_implementation="eager",
    )
    prompt_items = model.create_voice_clone_prompt(
        ref_audio=str(reference_path),
        ref_text=reference_text,
        x_vector_only_mode=False,
    )
    if len(prompt_items) != 1:
        raise RuntimeError("Expected exactly one reusable mother voice clone prompt.")
    prompt_item = prompt_items[0]
    prompt_path = output_dir / "family_mother_cast_v2.safetensors"
    prompt_artifact = save_voice_clone_prompt(
        prompt_item,
        prompt_path,
        reference_text=reference_text,
        reference_sha256=reference_artifact["sha256"],
    )

    seed_local_inference(args.seed)
    wavs, sample_rate = model.generate_voice_clone(
        text=audition_text,
        language="Korean",
        voice_clone_prompt=prompt_items,
        max_new_tokens=args.max_new_tokens,
    )
    audition_path = output_dir / "01_family_mother_voice_clone_validation.wav"
    sf.write(audition_path, wavs[0], sample_rate, format="WAV", subtype="PCM_16")
    audition_artifact = describe_wav(
        audition_path,
        position=1,
        voice=VOICE_ID,
        description="Cast version 2 family-mother voice clone validation line.",
    )
    audition_artifact["text"] = audition_text
    audition_artifact["seed"] = args.seed
    audition_artifact["pitchAnalysis"] = describe_wav_pitch(audition_path)

    manifest = {
        "schemaVersion": 1,
        "castVersion": CAST_VERSION,
        "roleId": ROLE_ID,
        "voiceId": VOICE_ID,
        "validationStatus": "awaiting-user-listening",
        "provider": "qwen3-tts-voice-clone",
        "model": MODEL_ID,
        "modelRevision": MODEL_REVISION,
        "runtimeVersion": runtime_version,
        "executionMode": "local-evaluation",
        "device": args.device,
        "dtype": args.dtype,
        "reference": {
            "manifest": str(reference_manifest_path.relative_to(Path.cwd())),
            "manifestSha256": sha256_file(reference_manifest_path),
            "voice": VOICE_ID,
            "filename": reference_path.name,
            "sha256": reference_artifact["sha256"],
            "text": reference_text,
        },
        "prompt": prompt_artifact,
        "generation": {
            "seed": args.seed,
            "maxNewTokens": args.max_new_tokens,
            "language": "Korean",
        },
        "artifacts": [audition_artifact],
        "officialWorkflow": "voice-design-then-icl-voice-clone",
    }
    manifest_path = write_manifest(output_dir, manifest)
    print(f"manifest {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
