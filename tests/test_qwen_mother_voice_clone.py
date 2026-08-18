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
    DEFAULT_AUDITION_TEXT,
    DEFAULT_SUBTALKER_TEMPERATURE,
    DEFAULT_TEMPERATURE,
    MODEL_ID,
    MODEL_REVISION,
    NON_STREAMING_MODE,
    QWEN_TTS_VERSION,
    ROLE_ID,
    VOICE_ID,
    load_reference_artifact,
    load_voice_clone_prompt,
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
    assert NON_STREAMING_MODE is True
    assert DEFAULT_TEMPERATURE == 0.9
    assert DEFAULT_SUBTALKER_TEMPERATURE == 0.9
    assert DEFAULT_AUDITION_TEXT == (
        "그래 오늘도 수고 많았어, 무슨 일이 있었는지 엄마한테 천천히 말해 봐."
    )
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


def test_initial_voice_clone_manifest_records_user_rejection():
    manifest_path = (
        REPOSITORY_ROOT
        / "artifacts/tts-clone-prompts/cast-v2/family-mother-qwen3-1.7b-base/manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["schemaVersion"] == 1
    assert manifest["castVersion"] == 2
    assert manifest["roleId"] == ROLE_ID
    assert manifest["voiceId"] == VOICE_ID
    assert manifest["validationStatus"] == "rejected-by-user"
    assert manifest["userFeedback"] == {
        "prosody": "unnatural-word-ending-intonation",
    }
    assert manifest["model"] == MODEL_ID
    assert manifest["modelRevision"] == MODEL_REVISION
    assert manifest["runtimeVersion"] == QWEN_TTS_VERSION
    assert manifest["officialWorkflow"] == "voice-design-then-icl-voice-clone"
    assert manifest["prompt"]["format"] == "safetensors"
    assert manifest["prompt"]["xVectorOnlyMode"] is False
    assert manifest["prompt"]["iclMode"] is True
    assert manifest["generation"]["nonStreamingMode"] is False
    assert manifest["generation"]["temperature"] == 0.9
    assert manifest["generation"]["subtalkerTemperature"] == 0.9
    assert len(manifest["prompt"]["sha256"]) == 64
    assert manifest["reference"]["sha256"] == (
        "a6ffd23a20a9858cd30b0af531b3e5e83786e53ee711797244b806f0fdeabf83"
    )
    assert len(manifest["artifacts"]) == 1
    assert len(manifest["artifacts"][0]["sha256"]) == 64


def test_controlled_non_streaming_candidate_reuses_the_rejected_prompt_exactly():
    initial_manifest_path = (
        REPOSITORY_ROOT
        / "artifacts/tts-clone-prompts/cast-v2/family-mother-qwen3-1.7b-base/manifest.json"
    )
    candidate_manifest_path = (
        REPOSITORY_ROOT / "artifacts/tts-clone-prompts/cast-v2/"
        "family-mother-qwen3-1.7b-base-non-streaming-icl/manifest.json"
    )
    initial = json.loads(initial_manifest_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_manifest_path.read_text(encoding="utf-8"))

    assert candidate["validationStatus"] == "rejected-by-user"
    assert candidate["userFeedback"] == {"prosody": "choppy-word-boundaries"}
    assert candidate["model"] == initial["model"] == MODEL_ID
    assert candidate["modelRevision"] == initial["modelRevision"] == MODEL_REVISION
    assert candidate["reference"] == initial["reference"]
    assert candidate["generation"]["seed"] == initial["generation"]["seed"]
    assert candidate["generation"]["maxNewTokens"] == initial["generation"]["maxNewTokens"]
    assert candidate["generation"]["language"] == initial["generation"]["language"]
    assert candidate["generation"]["nonStreamingMode"] is True
    assert initial["generation"]["nonStreamingMode"] is False
    assert candidate["prompt"]["sha256"] == initial["prompt"]["sha256"]
    assert candidate["prompt"]["reusedFromManifest"] == (
        "artifacts/tts-clone-prompts/cast-v2/family-mother-qwen3-1.7b-base/manifest.json"
    )


def test_connected_phrasing_candidate_changes_only_punctuation_from_previous_text():
    previous_manifest_path = (
        REPOSITORY_ROOT / "artifacts/tts-clone-prompts/cast-v2/"
        "family-mother-qwen3-1.7b-base-non-streaming-icl/manifest.json"
    )
    candidate_manifest_path = (
        REPOSITORY_ROOT / "artifacts/tts-clone-prompts/cast-v2/"
        "family-mother-qwen3-1.7b-base-connected-phrasing-icl/manifest.json"
    )
    previous = json.loads(previous_manifest_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_manifest_path.read_text(encoding="utf-8"))

    assert candidate["validationStatus"] == "rejected-by-user"
    assert candidate["userFeedback"] == {"prosody": "insufficient-intonation"}
    assert candidate["model"] == previous["model"] == MODEL_ID
    assert candidate["modelRevision"] == previous["modelRevision"] == MODEL_REVISION
    assert candidate["reference"] == previous["reference"]
    assert candidate["prompt"] == previous["prompt"]
    assert candidate["generation"] == previous["generation"]
    previous_text = previous["artifacts"][0]["text"]
    candidate_text = candidate["artifacts"][0]["text"]
    assert previous_text.translate(str.maketrans("", "", ",.")) == candidate_text
    assert " " in candidate_text
    assert not ({",", "."} & set(candidate_text))


def test_balanced_prosody_candidate_adds_one_natural_clause_boundary():
    connected_manifest_path = (
        REPOSITORY_ROOT / "artifacts/tts-clone-prompts/cast-v2/"
        "family-mother-qwen3-1.7b-base-connected-phrasing-icl/manifest.json"
    )
    candidate_manifest_path = (
        REPOSITORY_ROOT / "artifacts/tts-clone-prompts/cast-v2/"
        "family-mother-qwen3-1.7b-base-balanced-prosody-icl/manifest.json"
    )
    connected = json.loads(connected_manifest_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_manifest_path.read_text(encoding="utf-8"))

    assert candidate["validationStatus"] == "rejected-by-user"
    assert candidate["userFeedback"] == {"prosody": "insufficient-intonation-intensity"}
    assert candidate["model"] == connected["model"] == MODEL_ID
    assert candidate["modelRevision"] == connected["modelRevision"] == MODEL_REVISION
    assert candidate["reference"] == connected["reference"]
    assert candidate["prompt"] == connected["prompt"]
    assert candidate["generation"] == connected["generation"]
    connected_text = connected["artifacts"][0]["text"]
    candidate_text = candidate["artifacts"][0]["text"]
    assert candidate_text.replace(",", "") == connected_text
    assert candidate_text.count(",") == 1
    assert "." not in candidate_text
    assert "많았어, 무슨 일이" in candidate_text


def test_expressive_connected_candidate_uses_only_semantic_boundaries():
    balanced_manifest_path = (
        REPOSITORY_ROOT / "artifacts/tts-clone-prompts/cast-v2/"
        "family-mother-qwen3-1.7b-base-balanced-prosody-icl/manifest.json"
    )
    candidate_manifest_path = (
        REPOSITORY_ROOT / "artifacts/tts-clone-prompts/cast-v2/"
        "family-mother-qwen3-1.7b-base-expressive-connected-prosody-icl/manifest.json"
    )
    balanced = json.loads(balanced_manifest_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_manifest_path.read_text(encoding="utf-8"))

    assert candidate["validationStatus"] == "rejected-by-user"
    assert candidate["userFeedback"] == {"prosody": "insufficient-intonation-intensity"}
    assert candidate["model"] == balanced["model"] == MODEL_ID
    assert candidate["modelRevision"] == balanced["modelRevision"] == MODEL_REVISION
    assert candidate["reference"] == balanced["reference"]
    assert candidate["prompt"] == balanced["prompt"]
    assert candidate["generation"] == balanced["generation"]
    balanced_text = balanced["artifacts"][0]["text"]
    candidate_text = candidate["artifacts"][0]["text"]
    assert candidate_text.translate(str.maketrans("", "", ",.")) == balanced_text.replace(",", "")
    assert candidate_text.count(",") == 2
    assert candidate_text.count(".") == 1
    assert candidate_text.startswith("그래, 오늘도")
    assert "많았어, 무슨 일이" in candidate_text
    assert candidate_text.endswith("말해 봐.")


def test_enhanced_prosody_candidate_changes_only_main_talker_temperature():
    expressive_manifest_path = (
        REPOSITORY_ROOT / "artifacts/tts-clone-prompts/cast-v2/"
        "family-mother-qwen3-1.7b-base-expressive-connected-prosody-icl/manifest.json"
    )
    candidate_manifest_path = (
        REPOSITORY_ROOT / "artifacts/tts-clone-prompts/cast-v2/"
        "family-mother-qwen3-1.7b-base-enhanced-prosody-temperature-icl/manifest.json"
    )
    expressive = json.loads(expressive_manifest_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_manifest_path.read_text(encoding="utf-8"))

    assert candidate["validationStatus"] == "rejected-by-user"
    assert candidate["userFeedback"] == {
        "prosody": "insufficient-intonation-intensity",
        "continuity": "syllable-boundaries-too-distinct",
    }
    assert candidate["model"] == expressive["model"] == MODEL_ID
    assert candidate["modelRevision"] == expressive["modelRevision"] == MODEL_REVISION
    assert candidate["reference"] == expressive["reference"]
    assert candidate["prompt"] == expressive["prompt"]
    assert candidate["artifacts"][0]["text"] == expressive["artifacts"][0]["text"]
    expressive_generation = dict(expressive["generation"])
    candidate_generation = dict(candidate["generation"])
    assert expressive_generation.pop("temperature") == 0.9
    assert candidate_generation.pop("temperature") == 1.05
    assert candidate_generation == expressive_generation
    assert candidate_generation["subtalkerTemperature"] == 0.9


def test_high_prosody_smooth_candidate_changes_temperature_and_first_boundary():
    enhanced_manifest_path = (
        REPOSITORY_ROOT / "artifacts/tts-clone-prompts/cast-v2/"
        "family-mother-qwen3-1.7b-base-enhanced-prosody-temperature-icl/manifest.json"
    )
    candidate_manifest_path = (
        REPOSITORY_ROOT / "artifacts/tts-clone-prompts/cast-v2/"
        "family-mother-qwen3-1.7b-base-high-prosody-smooth-phrasing-icl/manifest.json"
    )
    enhanced = json.loads(enhanced_manifest_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_manifest_path.read_text(encoding="utf-8"))

    assert candidate["validationStatus"] == "approved-by-user"
    assert candidate["model"] == enhanced["model"] == MODEL_ID
    assert candidate["modelRevision"] == enhanced["modelRevision"] == MODEL_REVISION
    assert candidate["reference"] == enhanced["reference"]
    assert candidate["prompt"] == enhanced["prompt"]
    enhanced_generation = dict(enhanced["generation"])
    candidate_generation = dict(candidate["generation"])
    assert enhanced_generation.pop("temperature") == 1.05
    assert candidate_generation.pop("temperature") == 1.15
    assert candidate_generation == enhanced_generation
    assert candidate_generation["subtalkerTemperature"] == 0.9
    enhanced_text = enhanced["artifacts"][0]["text"]
    candidate_text = candidate["artifacts"][0]["text"]
    assert enhanced_text.replace("그래,", "그래", 1) == candidate_text
    assert candidate_text.count(",") == 1
    assert candidate_text.count(".") == 1
    assert candidate_text.startswith("그래 오늘도")
    assert "많았어, 무슨 일이" in candidate_text


def test_reusable_clone_prompt_rejects_missing_binary():
    manifest_path = (
        REPOSITORY_ROOT
        / "artifacts/tts-clone-prompts/cast-v2/family-mother-qwen3-1.7b-base/manifest.json"
    )
    prompt_path = manifest_path.parent / "family_mother_cast_v2.safetensors"
    if prompt_path.exists():
        pytest.skip("The local ignored prompt exists; missing-binary behavior is covered in CI.")

    with pytest.raises(RuntimeError, match="hash does not match"):
        load_voice_clone_prompt(manifest_path)
