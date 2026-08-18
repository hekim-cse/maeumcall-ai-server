from __future__ import annotations

import json
import wave
from pathlib import Path

import pytest

from scripts.generate_bark_korean_auditions import (
    KOREAN_VOICE_PRESETS as BARK_KOREAN_VOICE_PRESETS,
)
from scripts.generate_bark_korean_auditions import (
    MODEL_REVISION as BARK_MODEL_REVISION,
)
from scripts.generate_chatterbox_audition import (
    MODEL_FILES as CHATTERBOX_MODEL_FILES,
)
from scripts.generate_chatterbox_audition import (
    MODEL_REVISION as CHATTERBOX_MODEL_REVISION,
)
from scripts.generate_chatterbox_audition import (
    RUNTIME_SOURCE_REVISION as CHATTERBOX_SOURCE_REVISION,
)
from scripts.generate_chatterbox_audition import RUNTIME_VERSION as CHATTERBOX_VERSION
from scripts.generate_magpie_tts_auditions import MODEL_VERSION, SPEAKERS
from scripts.generate_melotts_audition import BERT_MODEL_REVISION, MELOTTS_SOURCE_REVISION
from scripts.tts_audition_common import (
    DEFAULT_AUDITION_TEXT,
    describe_wav,
    prepare_output_directory,
    write_manifest,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_audition_text_is_shared_across_providers():
    assert DEFAULT_AUDITION_TEXT == (
        "안녕하세요. 마음콜 통화 연습을 시작하겠습니다. 천천히 말씀해 주세요."
    )


def test_prepare_output_directory_rejects_every_existing_entry(tmp_path: Path):
    output_dir = tmp_path / "auditions"
    output_dir.mkdir()
    (output_dir / "manifest.json").write_text("{}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="must be empty"):
        prepare_output_directory(output_dir)


def test_describe_wav_records_reproducibility_metadata(tmp_path: Path):
    output_path = tmp_path / "voice.wav"
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16_000)
        wav_file.writeframes(b"\x00\x00" * 16_000)

    artifact = describe_wav(
        output_path,
        position=1,
        voice="voice",
        description="검증 음성",
    )

    assert artifact["sampleRate"] == 16_000
    assert artifact["channels"] == 1
    assert artifact["bitDepth"] == 16
    assert artifact["durationMs"] == 1_000
    assert len(artifact["sha256"]) == 64


def test_write_manifest_preserves_korean_text(tmp_path: Path):
    manifest_path = write_manifest(tmp_path, {"text": DEFAULT_AUDITION_TEXT})

    assert json.loads(manifest_path.read_text(encoding="utf-8"))["text"] == (DEFAULT_AUDITION_TEXT)


def test_candidate_runtime_versions_are_explicitly_pinned():
    assert MODEL_VERSION == "v2607"
    assert len(SPEAKERS) == 5
    assert len(MELOTTS_SOURCE_REVISION) == 40
    assert len(BERT_MODEL_REVISION) == 40
    assert CHATTERBOX_VERSION == "0.1.7"
    assert len(CHATTERBOX_SOURCE_REVISION) == 40
    assert len(CHATTERBOX_MODEL_REVISION) == 40
    assert "t3_mtl23ls_v3.safetensors" in CHATTERBOX_MODEL_FILES
    assert len(BARK_MODEL_REVISION) == 40
    assert BARK_KOREAN_VOICE_PRESETS == tuple(f"v2/ko_speaker_{index}" for index in range(10))


def test_committed_audition_manifests_share_the_same_contract():
    manifest_paths = (
        REPOSITORY_ROOT / "artifacts/tts-auditions/qwen3-tts-0.6b/manifest.json",
        REPOSITORY_ROOT / "artifacts/tts-auditions/magpie-v2607/manifest.json",
        REPOSITORY_ROOT / "artifacts/tts-auditions/melotts-korean/manifest.json",
        REPOSITORY_ROOT / "artifacts/tts-auditions/chatterbox-multilingual-v3/manifest.json",
        REPOSITORY_ROOT / "artifacts/tts-auditions/bark-small-korean/manifest.json",
    )
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in manifest_paths]

    assert {manifest["text"] for manifest in manifests} == {DEFAULT_AUDITION_TEXT}
    assert [len(manifest["artifacts"]) for manifest in manifests] == [9, 5, 1, 1, 10]
    assert manifests[0]["seed"] == 42
    assert "seed" not in manifests[1]
    assert manifests[2]["seed"] == 42
    assert manifests[3]["seed"] == 42
    assert manifests[3]["watermark"]["detected"] is True
    assert manifests[4]["baseSeed"] == 42
    assert all(
        len(artifact["sha256"]) == 64
        for manifest in manifests
        for artifact in manifest["artifacts"]
    )
