from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import wave
from pathlib import Path

import pytest

from scripts.build_qwen_mother_voice_clone import (
    CAST_VERSION,
    MODEL_ID,
    MODEL_REVISION,
    QWEN_TTS_VERSION,
    ROLE_ID,
    VOICE_ID,
    load_reference_artifact,
)

pytestmark = pytest.mark.unit

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _write_pcm16_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(24_000)
        wav_file.writeframes(b"\x00\x00" * 240)


def test_voice_clone_runtime_contract_is_pinned():
    assert MODEL_ID == "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
    assert MODEL_REVISION == "fd4b254389122332181a7c3db7f27e918eec64e3"
    assert QWEN_TTS_VERSION == "0.1.1"
    assert CAST_VERSION == 2
    assert ROLE_ID == "family_mother"
    assert VOICE_ID == "reference_warm_everyday_mature_age_restrained_prosody"


def test_reference_loader_requires_user_approval_exact_transcript_and_hash(tmp_path: Path):
    audio_path = tmp_path / "mother.wav"
    _write_pcm16_wav(audio_path)
    audio_sha256 = hashlib.sha256(audio_path.read_bytes()).hexdigest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "selectionStatus": "approved-by-user",
                "text": "기준 문장입니다.",
                "artifacts": [
                    {
                        "voice": VOICE_ID,
                        "filename": audio_path.name,
                        "sha256": audio_sha256,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    artifact, resolved_audio, transcript = load_reference_artifact(
        manifest_path,
        voice_id=VOICE_ID,
    )

    assert artifact["sha256"] == audio_sha256
    assert resolved_audio == audio_path
    assert transcript == "기준 문장입니다."


def test_reference_loader_rejects_unapproved_or_modified_audio(tmp_path: Path):
    audio_path = tmp_path / "mother.wav"
    _write_pcm16_wav(audio_path)
    manifest_path = tmp_path / "manifest.json"
    manifest = {
        "selectionStatus": "awaiting-user-selection",
        "text": "기준 문장입니다.",
        "artifacts": [
            {
                "voice": VOICE_ID,
                "filename": audio_path.name,
                "sha256": hashlib.sha256(audio_path.read_bytes()).hexdigest(),
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError, match="approved by the user"):
        load_reference_artifact(manifest_path, voice_id=VOICE_ID)

    manifest["selectionStatus"] = "approved-by-user"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    audio_path.write_bytes(audio_path.read_bytes() + b"changed")
    with pytest.raises(RuntimeError, match="hash does not match"):
        load_reference_artifact(manifest_path, voice_id=VOICE_ID)


def test_voice_clone_module_import_does_not_require_optional_tts_runtime():
    probe = """
import builtins
import importlib

original_import = builtins.__import__

def reject_optional_tts_runtime(name, *args, **kwargs):
    blocked = ("huggingface_hub", "qwen_tts", "safetensors", "soundfile", "torch")
    if name in blocked or name.startswith(tuple(f"{item}." for item in blocked)):
        raise ModuleNotFoundError(f"No module named '{name}'", name=name)
    return original_import(name, *args, **kwargs)

builtins.__import__ = reject_optional_tts_runtime
importlib.import_module("scripts.build_qwen_mother_voice_clone")
"""
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_committed_voice_clone_manifest_remains_a_pending_listening_gate():
    manifest_path = (
        REPOSITORY_ROOT
        / "artifacts/tts-clone-prompts/cast-v2/family-mother-qwen3-1.7b-base/manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["schemaVersion"] == 1
    assert manifest["castVersion"] == 2
    assert manifest["roleId"] == ROLE_ID
    assert manifest["voiceId"] == VOICE_ID
    assert manifest["validationStatus"] == "awaiting-user-listening"
    assert manifest["model"] == MODEL_ID
    assert manifest["modelRevision"] == MODEL_REVISION
    assert manifest["runtimeVersion"] == QWEN_TTS_VERSION
    assert manifest["officialWorkflow"] == "voice-design-then-icl-voice-clone"
    assert manifest["prompt"]["format"] == "safetensors"
    assert manifest["prompt"]["xVectorOnlyMode"] is False
    assert manifest["prompt"]["iclMode"] is True
    assert len(manifest["prompt"]["sha256"]) == 64
    assert manifest["reference"]["sha256"] == (
        "a6ffd23a20a9858cd30b0af531b3e5e83786e53ee711797244b806f0fdeabf83"
    )
    assert len(manifest["artifacts"]) == 1
    assert len(manifest["artifacts"][0]["sha256"]) == 64
