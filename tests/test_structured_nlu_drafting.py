from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

import pytest
from pydantic import ValidationError

import evals.structured_nlu.ai_origin_policy as ai_origin_policy
from evals.structured_nlu.ai_origin_policy import (
    AI_ORIGIN_TEXT_FINGERPRINTS_V1,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1,
    ai_origin_policy_fingerprint_v1,
    serialize_ai_origin_policy_v1,
)
from evals.structured_nlu.authoring import AuthoringGroup
from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.drafting import (
    AI_DRAFT_GENERATOR_ID,
    AI_DRAFT_PROVENANCE,
    AI_SUBAGENT_GENERATOR_ID,
    AIDraftSeedManifestV1,
    AISubagentCandidateManifestV1,
    build_ai_draft_seed_manifest_v1,
    build_ai_subagent_candidate_manifest_v1,
    render_ai_draft_human_review_packet_v1,
    render_ai_subagent_human_review_packet_v1,
    serialize_ai_draft_seed_manifest_v1,
    serialize_ai_draft_seed_schema_v1,
    serialize_ai_subagent_candidate_manifest_v1,
    serialize_ai_subagent_candidate_schema_v1,
)
from evals.structured_nlu.schema import ReviewStatus
from scripts.compile_structured_nlu_corpus import main as compile_corpus_main

REPO_ROOT = Path(__file__).parents[1]
DRAFT_SCHEMA_PATH = REPO_ROOT / "evals/structured_nlu/ai_draft_seed.schema.json"
DRAFT_SEED_PATH = REPO_ROOT / "evals/structured_nlu/drafts/ai-assisted-seeds.v1.json"
DRAFT_REVIEW_PACKET_PATH = REPO_ROOT / "evals/structured_nlu/drafts/human-review-packet.v1.md"
SUBAGENT_SCHEMA_PATH = REPO_ROOT / "evals/structured_nlu/ai_subagent_candidate.schema.json"
SUBAGENT_CANDIDATE_PATH = (
    REPO_ROOT / "evals/structured_nlu/drafts/subagent-assisted-candidates.v1.json"
)
SUBAGENT_REVIEW_PACKET_PATH = (
    REPO_ROOT / "evals/structured_nlu/drafts/subagent-human-review-packet.v1.md"
)
AI_ORIGIN_POLICY_PATH = REPO_ROOT / "evals/structured_nlu/manifests/ai-origin-policy.v1.json"


def test_ai_draft_seeds_cover_all_structured_nlu_scenarios() -> None:
    manifest = build_ai_draft_seed_manifest_v1()

    assert manifest.provenance == AI_DRAFT_PROVENANCE
    assert manifest.generator_id == AI_DRAFT_GENERATOR_ID
    assert manifest.human_review_required is True
    assert len(manifest.suggestions) == 16
    assert {suggestion.scenario_key for suggestion in manifest.suggestions} == set(
        EVALUATION_CONTRACTS
    )
    assert all(
        suggestion.primary_obligation.dimension is CoverageDimension.STATE_ACTION
        and suggestion.primary_obligation.value == "greeting->unknown"
        for suggestion in manifest.suggestions
    )


def test_ai_draft_seeds_pass_live_case_contract_as_unreviewed_proposals() -> None:
    manifest = build_ai_draft_seed_manifest_v1()

    assert all(
        suggestion.proposed_case.labels.user_action == "unknown"
        and suggestion.proposed_case.tags == ("hard_negative",)
        for suggestion in manifest.suggestions
    )
    assert all(
        all(value is None for value in suggestion.proposed_case.labels.fields.values())
        for suggestion in manifest.suggestions
    )


def test_ai_draft_manifest_cannot_be_loaded_as_official_authoring_source() -> None:
    payload = json.loads(serialize_ai_draft_seed_manifest_v1())

    with pytest.raises(ValidationError):
        AuthoringGroup.model_validate(payload)


def test_verbatim_ai_seed_cannot_be_relabelled_as_human_authored() -> None:
    suggestion = build_ai_draft_seed_manifest_v1().suggestions[0]
    payload = {
        "authoring_schema_version": 2,
        "conversation_group_id": "human-review-group",
        "scenario_key": suggestion.scenario_key,
        "provenance": "human_authored",
        "cases": [
            {
                **suggestion.proposed_case.model_dump(mode="json"),
                "id": "human-review-group.c1",
                "review_status": "draft",
            }
        ],
    }

    with pytest.raises(ValidationError, match="verbatim AI-origin text"):
        AuthoringGroup.model_validate(payload)


def test_ai_seed_ids_cannot_be_reused_in_human_authored_source() -> None:
    suggestion = build_ai_draft_seed_manifest_v1().suggestions[0]
    payload = {
        "authoring_schema_version": 2,
        "conversation_group_id": suggestion.conversation_group_id,
        "scenario_key": suggestion.scenario_key,
        "provenance": "human_authored",
        "cases": [
            {
                **suggestion.proposed_case.model_dump(mode="json"),
                "user_message": "사람이 새로 작성한 별개의 문장입니다.",
                "review_status": "draft",
            }
        ],
    }

    with pytest.raises(ValidationError, match="AI-origin ids"):
        AuthoringGroup.model_validate(payload)


def test_ai_origin_text_rejects_nfc_equivalent_and_cross_scenario_copies() -> None:
    seed_manifest = build_ai_draft_seed_manifest_v1()
    original = seed_manifest.suggestions[0]
    other = seed_manifest.suggestions[1]

    for scenario_key, user_message in (
        (original.scenario_key, unicodedata.normalize("NFD", original.proposed_case.user_message)),
        (other.scenario_key, original.proposed_case.user_message),
    ):
        template = original if scenario_key == original.scenario_key else other
        payload = {
            "authoring_schema_version": 2,
            "conversation_group_id": "human-renamed-group",
            "scenario_key": scenario_key,
            "provenance": "human_authored",
            "cases": [
                {
                    **template.proposed_case.model_dump(mode="json"),
                    "id": "human-renamed-group.c1",
                    "user_message": user_message,
                    "review_status": "draft",
                }
            ],
        }
        with pytest.raises(ValidationError, match="verbatim AI-origin text"):
            AuthoringGroup.model_validate(payload)


def test_ai_draft_manifest_rejects_profile_drift() -> None:
    payload = json.loads(serialize_ai_draft_seed_manifest_v1())
    payload["profile_fingerprint"] = "0" * 64

    with pytest.raises(ValidationError, match="profile fingerprint"):
        AIDraftSeedManifestV1.model_validate(payload)


def test_ai_draft_manifest_rejects_missing_scenario() -> None:
    payload = json.loads(serialize_ai_draft_seed_manifest_v1())
    payload["suggestions"].pop()

    with pytest.raises(ValidationError, match="exactly cover"):
        AIDraftSeedManifestV1.model_validate(payload)


def test_ai_draft_manifest_rejects_non_draft_promotion_attempt() -> None:
    payload = json.loads(serialize_ai_draft_seed_manifest_v1())
    payload["suggestions"][0]["proposed_case"]["review_status"] = ReviewStatus.ADJUDICATED

    with pytest.raises(ValidationError):
        AIDraftSeedManifestV1.model_validate(payload)


def test_committed_ai_draft_seed_artifacts_match_code_contract() -> None:
    assert DRAFT_SCHEMA_PATH.read_text(encoding="utf-8") == serialize_ai_draft_seed_schema_v1()
    assert DRAFT_SEED_PATH.read_text(encoding="utf-8") == serialize_ai_draft_seed_manifest_v1()


def test_human_review_packet_covers_all_suggestions_without_claiming_approval() -> None:
    packet = render_ai_draft_human_review_packet_v1()
    manifest = build_ai_draft_seed_manifest_v1()

    assert packet.count("### 사람 작성란") == 16
    assert packet.count("[ ] 최종 발화와 정답을 직접 작성했으며") == 16
    assert "공식 골든 corpus, 검수 원장 또는 사람 승인 증거가 아닙니다" in packet
    for index, suggestion in enumerate(manifest.suggestions, start=1):
        assert f"## {index:02d}. {suggestion.scenario_key}" in packet
        assert suggestion.suggestion_id in packet
        assert suggestion.proposed_case.user_message in packet


def test_committed_human_review_packet_matches_all_ai_seeds() -> None:
    assert (
        DRAFT_REVIEW_PACKET_PATH.read_text(encoding="utf-8")
        == render_ai_draft_human_review_packet_v1()
    )


def test_subagent_candidates_cover_all_scenarios_without_claiming_human_authorship() -> None:
    manifest = build_ai_subagent_candidate_manifest_v1()
    seed_messages = {
        suggestion.proposed_case.user_message
        for suggestion in build_ai_draft_seed_manifest_v1().suggestions
    }

    assert manifest.provenance == AI_DRAFT_PROVENANCE
    assert manifest.generator_id == AI_SUBAGENT_GENERATOR_ID
    assert manifest.human_review_required is True
    assert manifest.automatic_promotion_allowed is False
    assert len(AI_ORIGIN_TEXT_FINGERPRINTS_V1) == 32
    assert len(manifest.suggestions) == 16
    assert {suggestion.scenario_key for suggestion in manifest.suggestions} == set(
        EVALUATION_CONTRACTS
    )
    assert all(
        suggestion.proposed_case.user_message not in seed_messages
        and suggestion.proposed_case.labels.user_action == "unknown"
        and suggestion.proposed_case.tags == ("hard_negative",)
        and suggestion.drafting_rationale
        for suggestion in manifest.suggestions
    )


def test_subagent_candidate_manifest_cannot_be_loaded_as_authoring_source() -> None:
    payload = json.loads(serialize_ai_subagent_candidate_manifest_v1())

    with pytest.raises(ValidationError):
        AuthoringGroup.model_validate(payload)


def test_verbatim_subagent_candidate_cannot_be_relabelled_or_moved() -> None:
    manifest = build_ai_subagent_candidate_manifest_v1()
    candidate = manifest.suggestions[0]
    other = manifest.suggestions[1]

    for template in (candidate, other):
        payload = {
            "authoring_schema_version": 2,
            "conversation_group_id": "human-renamed-candidate",
            "scenario_key": template.scenario_key,
            "provenance": "human_authored",
            "cases": [
                {
                    **template.proposed_case.model_dump(mode="json"),
                    "id": "human-renamed-candidate.c1",
                    "user_message": unicodedata.normalize(
                        "NFD", candidate.proposed_case.user_message
                    ),
                    "review_status": "draft",
                }
            ],
        }
        with pytest.raises(ValidationError, match="verbatim AI-origin text"):
            AuthoringGroup.model_validate(payload)


def test_subagent_manifest_rejects_missing_scenario_and_profile_drift() -> None:
    payload = json.loads(serialize_ai_subagent_candidate_manifest_v1())
    payload["suggestions"].pop()
    with pytest.raises(ValidationError, match="exactly cover"):
        AISubagentCandidateManifestV1.model_validate(payload)


def test_subagent_manifest_rejects_nfc_duplicates_and_fixed_content_drift() -> None:
    seed = build_ai_draft_seed_manifest_v1().suggestions[0]
    payload = json.loads(serialize_ai_subagent_candidate_manifest_v1())
    payload["suggestions"][0]["proposed_case"]["user_message"] = unicodedata.normalize(
        "NFD", seed.proposed_case.user_message
    )
    with pytest.raises(ValidationError, match="message does not match the V1 policy"):
        AISubagentCandidateManifestV1.model_validate(payload)

    payload = json.loads(serialize_ai_subagent_candidate_manifest_v1())
    first_message = payload["suggestions"][0]["proposed_case"]["user_message"]
    payload["suggestions"][1]["proposed_case"]["user_message"] = unicodedata.normalize(
        "NFD", first_message
    )
    with pytest.raises(ValidationError, match="unique after NFC normalization"):
        AISubagentCandidateManifestV1.model_validate(payload)

    payload = json.loads(serialize_ai_subagent_candidate_manifest_v1())
    payload["suggestions"][0]["suggestion_id"] = "human-renamed-candidate"
    with pytest.raises(ValidationError, match="suggestion id"):
        AISubagentCandidateManifestV1.model_validate(payload)

    payload = json.loads(serialize_ai_subagent_candidate_manifest_v1())
    hospital = next(
        item for item in payload["suggestions"] if item["scenario_key"] == "예약:병원 예약"
    )
    hospital["proposed_case"]["labels"]["intent"] = "reservation"
    with pytest.raises(ValidationError, match="proposed case drifted"):
        AISubagentCandidateManifestV1.model_validate(payload)

    payload = json.loads(serialize_ai_subagent_candidate_manifest_v1())
    payload["profile_fingerprint"] = "0" * 64
    with pytest.raises(ValidationError, match="profile fingerprint"):
        AISubagentCandidateManifestV1.model_validate(payload)


def test_committed_subagent_artifacts_match_code_contract() -> None:
    assert (
        SUBAGENT_SCHEMA_PATH.read_text(encoding="utf-8")
        == serialize_ai_subagent_candidate_schema_v1()
    )
    assert (
        SUBAGENT_CANDIDATE_PATH.read_text(encoding="utf-8")
        == serialize_ai_subagent_candidate_manifest_v1()
    )
    assert (
        SUBAGENT_REVIEW_PACKET_PATH.read_text(encoding="utf-8")
        == render_ai_subagent_human_review_packet_v1()
    )
    assert ai_origin_policy_fingerprint_v1() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1
    assert AI_ORIGIN_POLICY_PATH.read_text(encoding="utf-8") == serialize_ai_origin_policy_v1()


def test_ai_origin_policy_fingerprint_includes_reserved_id_prefixes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = ai_origin_policy_fingerprint_v1()

    monkeypatch.setattr(ai_origin_policy, "AI_ORIGIN_ID_PREFIXES_V1", ("ai-different-",))

    assert ai_origin_policy_fingerprint_v1() != baseline


def test_subagent_review_packet_keeps_all_candidates_unreviewed() -> None:
    packet = render_ai_subagent_human_review_packet_v1()
    manifest = build_ai_subagent_candidate_manifest_v1()

    assert packet.count("### 사람 작성란") == 16
    assert packet.count("발화·정답·근거를 직접 작성했으며") == 16
    assert "그대로 복사하면 human_authored 골든 데이터가 될 수 없습니다" in packet
    for suggestion in manifest.suggestions:
        assert suggestion.proposed_case.user_message in packet
        assert suggestion.drafting_rationale in packet


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("draft-schema", serialize_ai_draft_seed_schema_v1),
        ("draft-seeds", serialize_ai_draft_seed_manifest_v1),
        ("draft-review-packet", render_ai_draft_human_review_packet_v1),
        ("draft-subagent-schema", serialize_ai_subagent_candidate_schema_v1),
        ("draft-subagent-candidates", serialize_ai_subagent_candidate_manifest_v1),
        ("draft-subagent-review-packet", render_ai_subagent_human_review_packet_v1),
        ("ai-origin-policy", serialize_ai_origin_policy_v1),
    ],
)
def test_ai_draft_cli_writes_deterministic_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    expected,
) -> None:
    output = tmp_path / f"{command}.json"
    monkeypatch.setattr(sys, "argv", ["compile_structured_nlu_corpus", command, str(output)])

    assert compile_corpus_main() == 0
    assert output.read_text(encoding="utf-8") == expected()


@pytest.mark.parametrize(
    ("command", "path"),
    [
        ("check-draft-schema", DRAFT_SCHEMA_PATH),
        ("check-draft-seeds", DRAFT_SEED_PATH),
        ("check-draft-review-packet", DRAFT_REVIEW_PACKET_PATH),
        ("check-draft-subagent-schema", SUBAGENT_SCHEMA_PATH),
        ("check-draft-subagent-candidates", SUBAGENT_CANDIDATE_PATH),
        ("check-draft-subagent-review-packet", SUBAGENT_REVIEW_PACKET_PATH),
        ("check-ai-origin-policy", AI_ORIGIN_POLICY_PATH),
    ],
)
def test_ai_draft_cli_checks_committed_artifact(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    path: Path,
) -> None:
    monkeypatch.setattr(sys, "argv", ["compile_structured_nlu_corpus", command, str(path)])

    assert compile_corpus_main() == 0
