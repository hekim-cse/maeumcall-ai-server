from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.structured_nlu.ai_origin_policy import (
    AI_ORIGIN_TEXT_FINGERPRINTS_V8,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V2,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V3,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V4,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V5,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V6,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V7,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V8,
    ai_origin_policy_descriptor,
    ai_origin_policy_fingerprint_v1,
    ai_origin_policy_fingerprint_v2,
    ai_origin_policy_fingerprint_v3,
    ai_origin_policy_fingerprint_v4,
    ai_origin_policy_fingerprint_v5,
    ai_origin_policy_fingerprint_v6,
    ai_origin_policy_fingerprint_v7,
    ai_origin_policy_fingerprint_v8,
    ai_origin_policy_payload_v7,
    ai_origin_policy_payload_v8,
    is_verbatim_ai_origin_text_for_policy,
    serialize_ai_origin_policy_schema_v8,
    serialize_ai_origin_policy_v8,
)
from evals.structured_nlu.authoring import AuthoringGroup
from evals.structured_nlu.coverage_candidate_policy_v7 import COVERAGE_CANDIDATE_SPECS_V7

ROOT = Path(__file__).resolve().parents[1]
POLICY_ROOT = ROOT / "evals/structured_nlu"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _authoring_payload() -> dict[str, object]:
    spec = next(iter(COVERAGE_CANDIDATE_SPECS_V7.values()))
    return {
        "authoring_schema_version": 2,
        "conversation_group_id": "human-policy-v8-replay",
        "scenario_key": spec.scenario_key,
        "provenance": "human_authored",
        "cases": [
            {
                "id": "human-policy-v8-replay.c1",
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


def test_policy_v8_is_the_exact_additive_202_entry_policy() -> None:
    v7_by_id = {entry["origin_id"]: entry for entry in ai_origin_policy_payload_v7()["entries"]}
    v8_entries = ai_origin_policy_payload_v8()["entries"]
    v8_by_id = {entry["origin_id"]: entry for entry in v8_entries}

    assert len(v7_by_id) == 175
    assert len(v8_by_id) == len(AI_ORIGIN_TEXT_FINGERPRINTS_V8) == 202
    assert all(v8_by_id[origin_id] == entry for origin_id, entry in v7_by_id.items())
    assert sum(origin_id.startswith("ai-coverage-v7-") for origin_id in v8_by_id) == 27
    assert {
        entry["origin_kind"]
        for origin_id, entry in v8_by_id.items()
        if origin_id.startswith("ai-coverage-v7-")
    } == {"coverage_candidate_batch_007"}
    assert ai_origin_policy_fingerprint_v8() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V8
    assert ai_origin_policy_descriptor(8).policy_fingerprint == (
        EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V8
    )


def test_policy_v8_artifact_and_schema_are_deterministic() -> None:
    assert (POLICY_ROOT / "manifests/ai-origin-policy.v8.json").read_text() == (
        serialize_ai_origin_policy_v8()
    )
    assert (POLICY_ROOT / "ai_origin_policy.schema.v8.json").read_text() == (
        serialize_ai_origin_policy_schema_v8()
    )


@pytest.mark.parametrize(
    ("write_command", "check_command", "serializer"),
    [
        (
            "ai-origin-policy-v8",
            "check-ai-origin-policy-v8",
            serialize_ai_origin_policy_v8,
        ),
        (
            "ai-origin-policy-schema-v8",
            "check-ai-origin-policy-schema-v8",
            serialize_ai_origin_policy_schema_v8,
        ),
    ],
)
def test_policy_v8_cli_writes_and_checks_exact_create_only_artifacts(
    tmp_path: Path,
    write_command: str,
    check_command: str,
    serializer,
) -> None:
    output = tmp_path / f"{write_command}.json"
    base = [sys.executable, "-m", "scripts.compile_structured_nlu_corpus"]

    subprocess.run([*base, write_command, str(output)], cwd=ROOT, check=True)
    assert output.read_text(encoding="utf-8") == serializer()
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

    regular = tmp_path / f"regular-{write_command}.json"
    regular.write_text(serializer(), encoding="utf-8")
    symlink = tmp_path / f"symlink-{write_command}.json"
    symlink.symlink_to(regular)
    linked = subprocess.run(
        [*base, check_command, str(symlink)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert linked.returncode != 0


def test_policy_v8_preserves_every_historical_policy_and_freeze_schema() -> None:
    assert ai_origin_policy_fingerprint_v1() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1
    assert ai_origin_policy_fingerprint_v2() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V2
    assert ai_origin_policy_fingerprint_v3() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V3
    assert ai_origin_policy_fingerprint_v4() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V4
    assert ai_origin_policy_fingerprint_v5() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V5
    assert ai_origin_policy_fingerprint_v6() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V6
    assert ai_origin_policy_fingerprint_v7() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V7
    expected_hashes = {
        "manifests/ai-origin-policy.v1.json": "d0fc9864c17e56f90d8392479cba39628351b9654c2f05fed419c459028d239c",
        "manifests/ai-origin-policy.v2.json": "e6d758fed6309ffeaa7b47ccd56dec257f7606cfdd4c0e40cf2bf81ac1f4eebc",
        "manifests/ai-origin-policy.v3.json": "011869376751dbe0584f65d5c59e3545b796ec2d93c0cd0fc88901c7ad1195ea",
        "manifests/ai-origin-policy.v4.json": "f96afea477612853305fdee8fe8782dbe6815c754890908463a8a4b09709016c",
        "manifests/ai-origin-policy.v5.json": "5ed38f1013d15351b25c31a728520dbe91d68829a8b81b4650f20b3d8a3d3bc3",
        "manifests/ai-origin-policy.v6.json": "16505efbac2d6082a306a6d6ffa82e695f326834e640363e790dd0c70b1462e8",
        "manifests/ai-origin-policy.v7.json": "9598c5cd27f16acc2bd008378d4222538ce517dcd20555e20323d738258cf60c",
        "ai_origin_policy.schema.v7.json": "0f95b6610c9292afc39193576b9166f6ee9a42cca99f78105627432f21cabce6",
        "freeze_record.schema.json": "195e1457f2860e1c493db38eb8992f8c2b0ac79e19f2488346f3a6e65ae046e1",
    }
    assert {
        relative: _sha256(POLICY_ROOT / relative) for relative in expected_hashes
    } == expected_hashes


def test_authoring_defaults_to_v8_while_policy_v7_remains_replayable() -> None:
    payload = _authoring_payload()
    message = next(iter(COVERAGE_CANDIDATE_SPECS_V7.values())).user_message

    assert not is_verbatim_ai_origin_text_for_policy(message, 7)
    assert is_verbatim_ai_origin_text_for_policy(message, 8)
    AuthoringGroup.model_validate(payload, context={"ai_origin_policy_schema_version": 0})
    AuthoringGroup.model_validate(payload, context={"ai_origin_policy_schema_version": 7})
    with pytest.raises(ValidationError, match="verbatim AI-origin text"):
        AuthoringGroup.model_validate(payload)
    with pytest.raises(ValidationError, match="verbatim AI-origin text"):
        AuthoringGroup.model_validate(payload, context={"ai_origin_policy_schema_version": 8})
