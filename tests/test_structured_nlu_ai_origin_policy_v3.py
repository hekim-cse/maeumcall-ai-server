from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.structured_nlu.ai_origin_policy import (
    AI_ORIGIN_TEXT_FINGERPRINTS_V1,
    AI_ORIGIN_TEXT_FINGERPRINTS_V2,
    AI_ORIGIN_TEXT_FINGERPRINTS_V3,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V2,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V3,
    ai_origin_policy_descriptor,
    ai_origin_policy_fingerprint_v1,
    ai_origin_policy_fingerprint_v2,
    ai_origin_policy_fingerprint_v3,
    ai_origin_policy_payload_v2,
    ai_origin_policy_payload_v3,
    is_reserved_ai_origin_id_for_policy,
    is_verbatim_ai_origin_text_for_policy,
    serialize_ai_origin_policy_schema_v3,
    serialize_ai_origin_policy_v1,
    serialize_ai_origin_policy_v2,
    serialize_ai_origin_policy_v3,
)
from evals.structured_nlu.authoring import AuthoringGroup
from evals.structured_nlu.coverage_candidate_policy import COVERAGE_CANDIDATE_SPECS_V1
from evals.structured_nlu.coverage_candidate_policy_v2 import COVERAGE_CANDIDATE_SPECS_V2
from evals.structured_nlu.draft_seed_policy import AI_DRAFT_SEED_SPECS_V1

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "evals/structured_nlu/manifests"


def _authoring_payload() -> dict[str, object]:
    spec = next(iter(COVERAGE_CANDIDATE_SPECS_V2.values()))
    return {
        "authoring_schema_version": 2,
        "conversation_group_id": "human-policy-replay",
        "scenario_key": spec.scenario_key,
        "provenance": "human_authored",
        "cases": [
            {
                "id": "human-policy-replay.c1",
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


def test_policy_v3_is_strictly_additive_and_preserves_v1_v2() -> None:
    v2_entries = ai_origin_policy_payload_v2()["entries"]
    v3_entries = ai_origin_policy_payload_v3()["entries"]

    assert ai_origin_policy_fingerprint_v1() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1
    assert ai_origin_policy_fingerprint_v2() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V2
    assert ai_origin_policy_fingerprint_v3() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V3
    assert len(AI_ORIGIN_TEXT_FINGERPRINTS_V1) == 32
    assert len(AI_ORIGIN_TEXT_FINGERPRINTS_V2) == 56
    assert len(AI_ORIGIN_TEXT_FINGERPRINTS_V3) == 60
    assert set(map(str, v2_entries)) <= set(map(str, v3_entries))
    assert sum(entry["origin_id"].startswith("ai-coverage-v2-") for entry in v3_entries) == 4


def test_policy_artifacts_and_v3_schema_are_deterministic() -> None:
    assert (MANIFESTS / "ai-origin-policy.v1.json").read_text() == serialize_ai_origin_policy_v1()
    assert (MANIFESTS / "ai-origin-policy.v2.json").read_text() == serialize_ai_origin_policy_v2()
    assert (MANIFESTS / "ai-origin-policy.v3.json").read_text() == serialize_ai_origin_policy_v3()
    assert (ROOT / "evals/structured_nlu/ai_origin_policy.schema.v3.json").read_text() == (
        serialize_ai_origin_policy_schema_v3()
    )


def test_authoring_default_rejects_v3_text_but_historical_dispatch_is_immutable() -> None:
    payload = _authoring_payload()

    with pytest.raises(ValidationError, match="verbatim AI-origin text"):
        AuthoringGroup.model_validate(payload)
    AuthoringGroup.model_validate(payload, context={"ai_origin_policy_schema_version": 2})
    AuthoringGroup.model_validate(payload, context={"ai_origin_policy_schema_version": 0})
    with pytest.raises(ValidationError, match="unsupported AI-origin policy"):
        AuthoringGroup.model_validate(payload, context={"ai_origin_policy_schema_version": 8})


@pytest.mark.parametrize("version", [True, "3", 3.0, None, -1])
def test_authoring_rejects_invalid_policy_version_types(version) -> None:
    with pytest.raises(ValidationError, match="unsupported AI-origin policy"):
        AuthoringGroup.model_validate(
            _authoring_payload(),
            context={"ai_origin_policy_schema_version": version},
        )


@pytest.mark.parametrize("version", [True, "3", 0, 8])
def test_policy_descriptor_rejects_unregistered_versions(version) -> None:
    with pytest.raises(ValueError, match="unsupported AI-origin policy"):
        ai_origin_policy_descriptor(version)


def test_policy_dispatcher_preserves_each_additive_history_boundary() -> None:
    seed = next(iter(AI_DRAFT_SEED_SPECS_V1.values())).user_message
    coverage_v1 = next(iter(COVERAGE_CANDIDATE_SPECS_V1.values())).user_message
    coverage_v2 = next(iter(COVERAGE_CANDIDATE_SPECS_V2.values())).user_message

    assert is_verbatim_ai_origin_text_for_policy(seed, 1)
    assert is_verbatim_ai_origin_text_for_policy(seed, 2)
    assert is_verbatim_ai_origin_text_for_policy(seed, 3)
    assert not is_verbatim_ai_origin_text_for_policy(coverage_v1, 1)
    assert is_verbatim_ai_origin_text_for_policy(coverage_v1, 2)
    assert is_verbatim_ai_origin_text_for_policy(coverage_v1, 3)
    assert not is_verbatim_ai_origin_text_for_policy(coverage_v2, 1)
    assert not is_verbatim_ai_origin_text_for_policy(coverage_v2, 2)
    assert is_verbatim_ai_origin_text_for_policy(coverage_v2, 3)
    assert is_reserved_ai_origin_id_for_policy("ai-seed-example", 1)
    assert not is_reserved_ai_origin_id_for_policy("ai-coverage-v1-example", 1)
    assert is_reserved_ai_origin_id_for_policy("ai-coverage-v1-example", 2)
    assert is_reserved_ai_origin_id_for_policy("ai-coverage-v2-example", 3)


@pytest.mark.parametrize(
    ("write_command", "check_command", "expected"),
    [
        ("ai-origin-policy-v3", "check-ai-origin-policy-v3", serialize_ai_origin_policy_v3),
        (
            "ai-origin-policy-schema-v3",
            "check-ai-origin-policy-schema-v3",
            serialize_ai_origin_policy_schema_v3,
        ),
    ],
)
def test_policy_v3_cli_writes_and_checks_exact_artifacts(
    tmp_path: Path,
    write_command: str,
    check_command: str,
    expected,
) -> None:
    output = tmp_path / f"{write_command}.json"
    base = [sys.executable, "-m", "scripts.compile_structured_nlu_corpus"]

    subprocess.run([*base, write_command, str(output)], cwd=ROOT, check=True)
    assert output.read_text(encoding="utf-8") == expected()
    subprocess.run([*base, check_command, str(output)], cwd=ROOT, check=True)

    original = output.read_bytes()
    overwrite = subprocess.run(
        [*base, write_command, str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert overwrite.returncode != 0
    assert output.read_bytes() == original

    output.write_text("{}\n", encoding="utf-8")
    stale = subprocess.run(
        [*base, check_command, str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert stale.returncode != 0
