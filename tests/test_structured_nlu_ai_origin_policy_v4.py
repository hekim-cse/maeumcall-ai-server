from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.structured_nlu.ai_origin_policy import (
    AI_ORIGIN_TEXT_FINGERPRINTS_V4,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V2,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V3,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V4,
    ai_origin_policy_descriptor,
    ai_origin_policy_fingerprint_v1,
    ai_origin_policy_fingerprint_v2,
    ai_origin_policy_fingerprint_v3,
    ai_origin_policy_fingerprint_v4,
    ai_origin_policy_payload_v3,
    ai_origin_policy_payload_v4,
    is_verbatim_ai_origin_text_for_policy,
    serialize_ai_origin_policy_schema_v4,
    serialize_ai_origin_policy_v4,
)
from evals.structured_nlu.authoring import AuthoringGroup
from evals.structured_nlu.coverage_candidate_policy_v3 import COVERAGE_CANDIDATE_SPECS_V3

ROOT = Path(__file__).resolve().parents[1]
POLICY_ROOT = ROOT / "evals/structured_nlu"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _authoring_payload() -> dict[str, object]:
    spec = next(iter(COVERAGE_CANDIDATE_SPECS_V3.values()))
    return {
        "authoring_schema_version": 2,
        "conversation_group_id": "human-policy-v4-replay",
        "scenario_key": spec.scenario_key,
        "provenance": "human_authored",
        "cases": [
            {
                "id": "human-policy-v4-replay.c1",
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


def test_policy_v4_is_the_exact_additive_91_entry_policy() -> None:
    v3_by_id = {entry["origin_id"]: entry for entry in ai_origin_policy_payload_v3()["entries"]}
    v4_entries = ai_origin_policy_payload_v4()["entries"]
    v4_by_id = {entry["origin_id"]: entry for entry in v4_entries}

    assert len(v3_by_id) == 60
    assert len(v4_by_id) == len(AI_ORIGIN_TEXT_FINGERPRINTS_V4) == 91
    assert all(v4_by_id[origin_id] == entry for origin_id, entry in v3_by_id.items())
    assert sum(origin_id.startswith("ai-coverage-v3-") for origin_id in v4_by_id) == 31
    assert {
        entry["origin_kind"]
        for origin_id, entry in v4_by_id.items()
        if origin_id.startswith("ai-coverage-v3-")
    } == {"coverage_candidate_batch_003"}
    assert ai_origin_policy_fingerprint_v4() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V4
    assert ai_origin_policy_descriptor(4).policy_fingerprint == (
        EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V4
    )


def test_policy_v4_artifact_and_schema_are_deterministic() -> None:
    assert (POLICY_ROOT / "manifests/ai-origin-policy.v4.json").read_text() == (
        serialize_ai_origin_policy_v4()
    )
    assert (POLICY_ROOT / "ai_origin_policy.schema.v4.json").read_text() == (
        serialize_ai_origin_policy_schema_v4()
    )


def test_policy_v4_preserves_historical_policy_and_freeze_schema_bytes() -> None:
    assert ai_origin_policy_fingerprint_v1() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1
    assert ai_origin_policy_fingerprint_v2() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V2
    assert ai_origin_policy_fingerprint_v3() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V3
    assert _sha256(POLICY_ROOT / "manifests/ai-origin-policy.v1.json") == (
        "d0fc9864c17e56f90d8392479cba39628351b9654c2f05fed419c459028d239c"
    )
    assert _sha256(POLICY_ROOT / "manifests/ai-origin-policy.v2.json") == (
        "e6d758fed6309ffeaa7b47ccd56dec257f7606cfdd4c0e40cf2bf81ac1f4eebc"
    )
    assert _sha256(POLICY_ROOT / "manifests/ai-origin-policy.v3.json") == (
        "011869376751dbe0584f65d5c59e3545b796ec2d93c0cd0fc88901c7ad1195ea"
    )
    assert _sha256(POLICY_ROOT / "freeze_record.schema.json") == (
        "195e1457f2860e1c493db38eb8992f8c2b0ac79e19f2488346f3a6e65ae046e1"
    )


def test_authoring_current_policy_rejects_v4_text_while_v3_remains_replayable() -> None:
    payload = _authoring_payload()
    message = next(iter(COVERAGE_CANDIDATE_SPECS_V3.values())).user_message

    assert not is_verbatim_ai_origin_text_for_policy(message, 3)
    assert is_verbatim_ai_origin_text_for_policy(message, 4)
    AuthoringGroup.model_validate(payload, context={"ai_origin_policy_schema_version": 0})
    AuthoringGroup.model_validate(payload, context={"ai_origin_policy_schema_version": 3})
    with pytest.raises(ValidationError, match="verbatim AI-origin text"):
        AuthoringGroup.model_validate(payload)
    with pytest.raises(ValidationError, match="verbatim AI-origin text"):
        AuthoringGroup.model_validate(payload, context={"ai_origin_policy_schema_version": 4})
