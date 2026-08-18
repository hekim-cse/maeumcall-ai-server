from __future__ import annotations

import hashlib
import json
import math
import wave
from collections import Counter
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
from scripts.generate_qwen_mother_voice_design_auditions import (
    MODEL_REVISION as QWEN_VOICE_DESIGN_REVISION,
)
from scripts.generate_qwen_mother_voice_design_auditions import (
    MOTHER_VOICE_DESIGNS,
    MOTHER_VOICE_REFINEMENTS,
    REFERENCE_CALIBRATED_MOTHER_VOICE_DESIGNS,
    evaluate_pitch_against_reference,
    load_acoustic_reference,
)
from scripts.generate_qwen_role_casting_auditions import ROLE_AUDITIONS
from scripts.tts_audition_common import (
    DEFAULT_AUDITION_TEXT,
    describe_wav,
    describe_wav_pitch,
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


def test_describe_wav_pitch_measures_a_known_sine_wave(tmp_path: Path):
    import numpy as np

    sample_rate = 16_000
    expected_frequency = 160.0
    samples = np.array(
        [
            math.sin(2 * math.pi * expected_frequency * index / sample_rate)
            for index in range(sample_rate)
        ],
        dtype=np.float32,
    )
    output_path = tmp_path / "sine.wav"
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes((samples * 16_000).astype("<i2").tobytes())

    analysis = describe_wav_pitch(output_path)

    assert analysis["algorithm"] == "praat-autocorrelation"
    assert analysis["medianF0Hz"] == pytest.approx(expected_frequency, abs=1.0)
    assert analysis["voicedFrames"] > 0


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
    assert len(QWEN_VOICE_DESIGN_REVISION) == 40
    assert len(MOTHER_VOICE_DESIGNS) == 5
    assert len(MOTHER_VOICE_REFINEMENTS) == 4
    assert len(REFERENCE_CALIBRATED_MOTHER_VOICE_DESIGNS) == 3


def test_acoustic_reference_loader_accepts_only_the_mother_calibration_contract(
    tmp_path: Path,
):
    reference_path = tmp_path / "reference.json"
    reference_path.write_text(
        json.dumps(
            {
                "referenceContractVersion": 1,
                "purpose": "family-mother-candidate-acoustic-calibration",
                "dataset": {"id": 71558, "rawDataCommitted": False},
                "coverage": {"selectedSpeakers": 55},
                "privacy": {
                    "containsSpeakerIdentifiers": False,
                    "containsSourceFileNames": False,
                    "containsTranscripts": False,
                    "containsAudio": False,
                    "statisticsAreAggregateOnly": True,
                },
                "acousticReference": {
                    "speakerMedianF0Hz": {"p25": 187.1, "median": 203.3, "p75": 229.2}
                },
            }
        ),
        encoding="utf-8",
    )

    reference = load_acoustic_reference(reference_path)

    assert reference["p25F0Hz"] == 187.1
    assert reference["medianF0Hz"] == 203.3
    assert reference["p75F0Hz"] == 229.2
    assert len(str(reference["manifestSha256"])) == 64


def test_acoustic_reference_evaluation_is_a_screen_not_an_automatic_approval():
    reference = {
        "manifestSha256": "a" * 64,
        "p25F0Hz": 187.1,
        "medianF0Hz": 203.3,
        "p75F0Hz": 229.2,
    }

    within = evaluate_pitch_against_reference(196.9, reference)
    outside = evaluate_pitch_against_reference(162.4, reference)

    assert within["result"] == "within-reference-interquartile-range"
    assert outside["result"] == "outside-reference-interquartile-range"
    assert within["decisionBoundary"] == "acoustic-screening-only-requires-user-listening"


def test_acoustic_reference_loader_rejects_speaker_level_data(tmp_path: Path):
    reference_path = tmp_path / "reference.json"
    reference_path.write_text(
        json.dumps(
            {
                "referenceContractVersion": 1,
                "purpose": "family-mother-candidate-acoustic-calibration",
                "dataset": {"id": 71558, "rawDataCommitted": False},
                "coverage": {"selectedSpeakers": 55},
                "privacy": {
                    "containsSpeakerIdentifiers": True,
                    "containsSourceFileNames": False,
                    "containsTranscripts": False,
                    "containsAudio": False,
                    "statisticsAreAggregateOnly": False,
                },
                "acousticReference": {
                    "speakerMedianF0Hz": {"p25": 187.1, "median": 203.3, "p75": 229.2}
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="aggregate privacy contract"):
        load_acoustic_reference(reference_path)


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


def test_cast_v2_role_auditions_cover_only_roles_awaiting_selection():
    selection_path = REPOSITORY_ROOT / "artifacts/tts-casting/cast-v2-selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    bark_manifest = json.loads(
        (REPOSITORY_ROOT / "artifacts/tts-auditions/bark-small-korean/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    qwen_role_manifest = json.loads(
        (
            REPOSITORY_ROOT / "artifacts/tts-role-auditions/cast-v2/qwen3-tts/manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert selection["castVersion"] == 2
    assert selection["selectionStatus"] == "in-progress"
    approved_roles = {role["roleId"]: role for role in selection["approvedRoles"]}
    assert {
        role_id: (role["provider"], role["voice"]) for role_id, role in approved_roles.items()
    } == {
        "company_manager": ("bark-small", "ko_speaker_5"),
        "service_agent": ("qwen3-tts", "ryan"),
        "delivery_agent": ("qwen3-tts", "vivian"),
        "family_father": ("qwen3-tts", "aiden"),
    }
    assert approved_roles["family_father"]["personaId"] == "father"
    assert all(role["decision"] == "approved-by-user" for role in approved_roles.values())
    bark_voice = next(
        artifact for artifact in bark_manifest["artifacts"] if artifact["voice"] == "ko_speaker_5"
    )
    assert bark_voice["sha256"] == approved_roles["company_manager"]["sourceSha256"]
    qwen_artifacts = {
        (artifact["roleId"], artifact["voice"]): artifact
        for artifact in qwen_role_manifest["artifacts"]
    }
    for role_id, evaluated_role_id, voice in (
        ("service_agent", "service_agent", "ryan"),
        ("delivery_agent", "delivery_agent", "vivian"),
        ("family_father", "family_mother", "aiden"),
    ):
        assert (
            qwen_artifacts[(evaluated_role_id, voice)]["sha256"]
            == approved_roles[role_id]["sourceSha256"]
        )
    assert selection["rolesAwaitingSelection"] == [
        {
            "roleId": "family_mother",
            "categories": ["가족"],
            "personaId": "mother",
            "candidateProvider": "qwen3-tts-voice-design",
            "candidateManifests": [
                (
                    "artifacts/tts-role-auditions/cast-v2/"
                    "qwen3-voice-design-family-mother/manifest.json"
                ),
                (
                    "artifacts/tts-role-auditions/cast-v2/"
                    "qwen3-voice-design-family-mother-refinements/"
                    "lower-fuller-corrections/manifest.json"
                ),
                (
                    "artifacts/tts-role-auditions/cast-v2/"
                    "qwen3-voice-design-family-mother-reference-calibrated/manifest.json"
                ),
            ],
            "activeCandidateIds": [
                "natural_everyday",
                "reference_calm_reassuring",
                "reference_gentle_lived_in",
            ],
            "selectionReason": "awaiting-user-listening-after-aihub-multi-speaker-calibration",
        }
    ]
    rejected_candidates = {
        candidate["candidateId"]: candidate for candidate in selection["rejectedCandidates"]
    }
    assert selection["screenedCandidates"] == [
        {
            "roleId": "family_mother",
            "candidateId": "reference_warm_everyday",
            "parentCandidateId": "natural_everyday",
            "sourceArtifact": (
                "artifacts/tts-role-auditions/cast-v2/"
                "qwen3-voice-design-family-mother-reference-calibrated/"
                "01_reference_warm_everyday.wav"
            ),
            "sourceSha256": ("41d8d1c5c3296e0905430d712b007b0b95527373501abe708119689af5c1c9db"),
            "decision": "available-for-listening-not-shortlisted",
            "reason": "below-aihub-reference-interquartile-range",
            "acousticReferenceEvaluation": {
                "referenceP25F0Hz": 187.1,
                "referenceP75F0Hz": 229.2,
                "candidateMedianF0Hz": 168.3,
                "result": "outside-reference-interquartile-range",
                "decisionBoundary": "acoustic-screening-only-requires-user-listening",
            },
        }
    ]
    assert {
        candidate_id: candidate["decision"]
        for candidate_id, candidate in rejected_candidates.items()
    } == {
        "natural_everyday_mature_low": "rejected-by-user",
        "natural_everyday_contralto": "rejected-by-user",
        "natural_everyday_deep_alto": "rejected-by-pitch-contract",
        "natural_everyday_warm_husky": "rejected-by-pitch-contract",
    }
    assert all(
        candidate["pitchComparison"]["candidateMedianF0Hz"]
        > candidate["pitchComparison"]["parentMedianF0Hz"]
        for candidate_id, candidate in rejected_candidates.items()
        if candidate_id != "natural_everyday_contralto"
    )
    assert (
        rejected_candidates["natural_everyday_contralto"]["pitchComparison"]["candidateMedianF0Hz"]
        < rejected_candidates["natural_everyday_contralto"]["pitchComparison"]["parentMedianF0Hz"]
    )
    assert {tuple(role["categories"]) for role in selection["retainedRoles"]} == {
        ("교수님",),
        ("친구",),
        ("연인",),
    }
    role_coverage = {
        (role.get("roleId", "retained"), category, role.get("personaId"))
        for section in ("approvedRoles", "rolesAwaitingSelection", "retainedRoles")
        for role in selection[section]
        for category in role["categories"]
    }
    assert role_coverage == {
        ("service_agent", "예약", None),
        ("service_agent", "시청", None),
        ("service_agent", "고객센터", None),
        ("delivery_agent", "배달", None),
        ("family_father", "가족", "father"),
        ("family_mother", "가족", "mother"),
        ("company_manager", "회사", None),
        ("retained", "교수님", None),
        ("retained", "친구", None),
        ("retained", "연인", None),
    }


def test_committed_qwen_cast_v2_auditions_cover_every_voice_for_each_open_role():
    manifest_path = REPOSITORY_ROOT / "artifacts/tts-role-auditions/cast-v2/qwen3-tts/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["castVersion"] == 2
    assert manifest["selectionStatus"] == "awaiting-user-selection"
    assert manifest["modelRevision"] == "85e237c12c027371202489a0ec509ded67b5e4b5"
    assert manifest["baseSeed"] == 42
    assert len(manifest["artifacts"]) == len(ROLE_AUDITIONS) * 9
    assert Counter(artifact["roleId"] for artifact in manifest["artifacts"]) == {
        role.id: 9 for role in ROLE_AUDITIONS
    }
    expected_voices = {
        "aiden",
        "dylan",
        "eric",
        "ono_anna",
        "ryan",
        "serena",
        "sohee",
        "uncle_fu",
        "vivian",
    }
    for role in ROLE_AUDITIONS:
        role_artifacts = [
            artifact for artifact in manifest["artifacts"] if artifact["roleId"] == role.id
        ]
        assert {artifact["voice"] for artifact in role_artifacts} == expected_voices
        assert {artifact["text"] for artifact in role_artifacts} == {role.text}
        assert {tuple(artifact["categories"]) for artifact in role_artifacts} == {role.categories}
        assert all(len(artifact["sha256"]) == 64 for artifact in role_artifacts)


def test_committed_qwen_voice_design_manifest_matches_mother_candidates():
    manifest_path = (
        REPOSITORY_ROOT / "artifacts/tts-role-auditions/cast-v2/"
        "qwen3-voice-design-family-mother/manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["castVersion"] == 2
    assert manifest["roleId"] == "family_mother"
    assert manifest["selectionStatus"] == "awaiting-user-selection"
    assert manifest["provider"] == "qwen3-tts-voice-design"
    assert manifest["modelRevision"] == QWEN_VOICE_DESIGN_REVISION
    assert manifest["runtimeVersion"] == "0.1.1"
    assert manifest["baseSeed"] == 42
    assert manifest["seedStrategy"] == "base-seed-plus-stable-design-offset"
    assert manifest["designIds"] == [design.id for design in MOTHER_VOICE_DESIGNS]
    assert [artifact["voice"] for artifact in manifest["artifacts"]] == [
        design.id for design in MOTHER_VOICE_DESIGNS
    ]
    assert [artifact["description"] for artifact in manifest["artifacts"]] == [
        design.direction for design in MOTHER_VOICE_DESIGNS
    ]
    assert all(
        artifact["pitchAnalysis"]["algorithm"] == "praat-autocorrelation"
        for artifact in manifest["artifacts"]
    )
    assert all(len(artifact["sha256"]) == 64 for artifact in manifest["artifacts"])


def test_mother_voice_refinement_preserves_parent_candidate_lineage():
    manifest_path = (
        REPOSITORY_ROOT / "artifacts/tts-role-auditions/cast-v2/"
        "qwen3-voice-design-family-mother-refinements/"
        "natural-everyday-mature-low/manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    refinement = MOTHER_VOICE_REFINEMENTS[0]
    artifact = manifest["artifacts"][0]

    assert manifest["modelRevision"] == QWEN_VOICE_DESIGN_REVISION
    assert manifest["seedStrategy"] == "base-seed-plus-stable-design-offset"
    assert manifest["designIds"] == [refinement.id]
    assert artifact["voice"] == refinement.id
    assert artifact["description"] == refinement.direction
    assert artifact["parentCandidateId"] == refinement.parent_id == "natural_everyday"
    assert artifact["seed"] == 42 + refinement.seed_offset == 47
    assert artifact["pitchAnalysis"]["medianF0Hz"] == 237.1
    assert len(artifact["sha256"]) == 64


def test_lower_fuller_corrections_keep_only_the_candidate_with_lower_measured_pitch():
    manifest_path = (
        REPOSITORY_ROOT / "artifacts/tts-role-auditions/cast-v2/"
        "qwen3-voice-design-family-mother-refinements/"
        "lower-fuller-corrections/manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    refinements = MOTHER_VOICE_REFINEMENTS[1:]

    assert manifest["designIds"] == [design.id for design in refinements]
    assert [artifact["parentCandidateId"] for artifact in manifest["artifacts"]] == [
        design.parent_id for design in refinements
    ]
    measured_pitch = {
        artifact["voice"]: artifact["pitchAnalysis"]["medianF0Hz"]
        for artifact in manifest["artifacts"]
    }
    assert {
        candidate_id
        for candidate_id, median_f0_hz in measured_pitch.items()
        if median_f0_hz < 196.9
    } == {"natural_everyday_contralto"}


def test_reference_calibrated_mother_candidates_record_aggregate_screening():
    manifest_path = (
        REPOSITORY_ROOT / "artifacts/tts-role-auditions/cast-v2/"
        "qwen3-voice-design-family-mother-reference-calibrated/manifest.json"
    )
    reference_path = (
        REPOSITORY_ROOT / "artifacts/tts-role-auditions/cast-v2/family-mother-reference/"
        "aihub-71558-jeju-validation-v1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["designIds"] == [
        design.id for design in REFERENCE_CALIBRATED_MOTHER_VOICE_DESIGNS
    ]
    assert (
        manifest["acousticReference"]["manifestSha256"]
        == hashlib.sha256(reference_path.read_bytes()).hexdigest()
    )
    results = {
        artifact["voice"]: artifact["acousticReferenceEvaluation"]["result"]
        for artifact in manifest["artifacts"]
    }
    assert results == {
        "reference_warm_everyday": "outside-reference-interquartile-range",
        "reference_calm_reassuring": "within-reference-interquartile-range",
        "reference_gentle_lived_in": "within-reference-interquartile-range",
    }
    assert all(len(artifact["sha256"]) == 64 for artifact in manifest["artifacts"])
