from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.structured_nlu.ai_origin_policy import (
    AI_ORIGIN_TEXT_FINGERPRINTS_V7,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V2,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V3,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V4,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V5,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V6,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V7,
    ai_origin_policy_descriptor,
    ai_origin_policy_fingerprint_v1,
    ai_origin_policy_fingerprint_v2,
    ai_origin_policy_fingerprint_v3,
    ai_origin_policy_fingerprint_v4,
    ai_origin_policy_fingerprint_v5,
    ai_origin_policy_fingerprint_v6,
    ai_origin_policy_fingerprint_v7,
    ai_origin_policy_payload_v6,
    ai_origin_policy_payload_v7,
    is_verbatim_ai_origin_text_for_policy,
    serialize_ai_origin_policy_schema_v7,
    serialize_ai_origin_policy_v7,
)
from evals.structured_nlu.authoring import AuthoringGroup
from evals.structured_nlu.coverage_candidate_policy_v6 import COVERAGE_CANDIDATE_SPECS_V6

ROOT = Path(__file__).resolve().parents[1]
POLICY_ROOT = ROOT / "evals/structured_nlu"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _authoring_payload() -> dict[str, object]:
    spec = next(iter(COVERAGE_CANDIDATE_SPECS_V6.values()))
    return {
        "authoring_schema_version": 2,
        "conversation_group_id": "human-policy-v7-replay",
        "scenario_key": spec.scenario_key,
        "provenance": "human_authored",
        "cases": [
            {
                "id": "human-policy-v7-replay.c1",
                "conversation_state": spec.conversation_state,
                "current_fields": dict(spec.current_fields),
                "offered_alternative_times": list(spec.offered_alternative_times),
                "user_message": spec.user_message,
                "labels": {
                    "intent": spec.intent,
                    "fields": {
                        name: (None if values is None else {"accepted_values": list(values)})
                        for name, values in spec.fields
                    },
                    "user_action": spec.user_action,
                    "change_field": spec.change_field,
                },
                "tags": [tag.value for tag in spec.tags],
                "review_status": "draft",
            }
        ],
    }


def test_policy_v7_is_the_exact_additive_175_entry_policy() -> None:
    v6_by_id = {entry["origin_id"]: entry for entry in ai_origin_policy_payload_v6()["entries"]}
    v7_entries = ai_origin_policy_payload_v7()["entries"]
    v7_by_id = {entry["origin_id"]: entry for entry in v7_entries}

    assert len(v6_by_id) == 137
    assert len(v7_by_id) == len(AI_ORIGIN_TEXT_FINGERPRINTS_V7) == 175
    assert all(v7_by_id[origin_id] == entry for origin_id, entry in v6_by_id.items())
    assert sum(origin_id.startswith("ai-coverage-v6-") for origin_id in v7_by_id) == 38
    assert {
        entry["origin_kind"]
        for origin_id, entry in v7_by_id.items()
        if origin_id.startswith("ai-coverage-v6-")
    } == {"coverage_candidate_batch_006"}
    assert ai_origin_policy_fingerprint_v7() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V7
    assert ai_origin_policy_descriptor(7).policy_fingerprint == (
        EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V7
    )


def test_policy_v7_artifact_and_schema_are_deterministic() -> None:
    assert (POLICY_ROOT / "manifests/ai-origin-policy.v7.json").read_text() == (
        serialize_ai_origin_policy_v7()
    )
    assert (POLICY_ROOT / "ai_origin_policy.schema.v7.json").read_text() == (
        serialize_ai_origin_policy_schema_v7()
    )


def test_policy_v7_preserves_every_historical_policy_and_freeze_schema() -> None:
    assert ai_origin_policy_fingerprint_v1() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1
    assert ai_origin_policy_fingerprint_v2() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V2
    assert ai_origin_policy_fingerprint_v3() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V3
    assert ai_origin_policy_fingerprint_v4() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V4
    assert ai_origin_policy_fingerprint_v5() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V5
    assert ai_origin_policy_fingerprint_v6() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V6
    expected_hashes = {
        "manifests/ai-origin-policy.v1.json": "d0fc9864c17e56f90d8392479cba39628351b9654c2f05fed419c459028d239c",
        "manifests/ai-origin-policy.v2.json": "e6d758fed6309ffeaa7b47ccd56dec257f7606cfdd4c0e40cf2bf81ac1f4eebc",
        "manifests/ai-origin-policy.v3.json": "011869376751dbe0584f65d5c59e3545b796ec2d93c0cd0fc88901c7ad1195ea",
        "manifests/ai-origin-policy.v4.json": "f96afea477612853305fdee8fe8782dbe6815c754890908463a8a4b09709016c",
        "manifests/ai-origin-policy.v5.json": "5ed38f1013d15351b25c31a728520dbe91d68829a8b81b4650f20b3d8a3d3bc3",
        "manifests/ai-origin-policy.v6.json": "16505efbac2d6082a306a6d6ffa82e695f326834e640363e790dd0c70b1462e8",
        "ai_origin_policy.schema.v6.json": "2f4814033d1cc50e43eede2f594f6d7b356eb9b797a5e74928386f3c41cb0f18",
        "freeze_record.schema.json": "195e1457f2860e1c493db38eb8992f8c2b0ac79e19f2488346f3a6e65ae046e1",
    }
    assert {
        relative: _sha256(POLICY_ROOT / relative) for relative in expected_hashes
    } == expected_hashes


def test_authoring_current_policy_rejects_v7_text_while_v6_remains_replayable() -> None:
    payload = _authoring_payload()
    message = next(iter(COVERAGE_CANDIDATE_SPECS_V6.values())).user_message

    assert not is_verbatim_ai_origin_text_for_policy(message, 6)
    assert is_verbatim_ai_origin_text_for_policy(message, 7)
    AuthoringGroup.model_validate(payload, context={"ai_origin_policy_schema_version": 0})
    AuthoringGroup.model_validate(payload, context={"ai_origin_policy_schema_version": 6})
    with pytest.raises(ValidationError, match="verbatim AI-origin text"):
        AuthoringGroup.model_validate(payload)
    with pytest.raises(ValidationError, match="verbatim AI-origin text"):
        AuthoringGroup.model_validate(payload, context={"ai_origin_policy_schema_version": 7})
