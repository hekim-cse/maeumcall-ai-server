from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.structured_nlu.authoring import AuthoringGroup
from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.drafting import (
    AI_DRAFT_GENERATOR_ID,
    AI_DRAFT_PROVENANCE,
    AIDraftSeedManifestV1,
    build_ai_draft_seed_manifest_v1,
    serialize_ai_draft_seed_manifest_v1,
    serialize_ai_draft_seed_schema_v1,
)
from evals.structured_nlu.schema import ReviewStatus
from scripts.compile_structured_nlu_corpus import main as compile_corpus_main

REPO_ROOT = Path(__file__).parents[1]
DRAFT_SCHEMA_PATH = REPO_ROOT / "evals/structured_nlu/ai_draft_seed.schema.json"
DRAFT_SEED_PATH = REPO_ROOT / "evals/structured_nlu/drafts/ai-assisted-seeds.v1.json"


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

    with pytest.raises(ValidationError, match="verbatim AI draft seed text"):
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

    with pytest.raises(ValidationError, match="AI draft seed ids"):
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


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("draft-schema", serialize_ai_draft_seed_schema_v1),
        ("draft-seeds", serialize_ai_draft_seed_manifest_v1),
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
    ],
)
def test_ai_draft_cli_checks_committed_artifact(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    path: Path,
) -> None:
    monkeypatch.setattr(sys, "argv", ["compile_structured_nlu_corpus", command, str(path)])

    assert compile_corpus_main() == 0
