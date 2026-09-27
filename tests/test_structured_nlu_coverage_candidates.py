from __future__ import annotations

import json
import subprocess
import sys
import unicodedata
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from evals.structured_nlu.ai_origin_policy import (
    AI_ORIGIN_TEXT_FINGERPRINTS_V2,
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V2,
    ai_origin_policy_fingerprint_v2,
    serialize_ai_origin_policy_v2,
)
from evals.structured_nlu.authoring import AuthoringGroup, compile_authoring_directory
from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.coverage_progress import build_development_coverage_progress
from evals.structured_nlu.drafting import (
    AI_COVERAGE_CANDIDATE_GENERATOR_ID,
    AI_DRAFT_PROVENANCE,
    AICoverageCandidateManifestV1,
    build_ai_coverage_candidate_manifest_v1,
    render_ai_coverage_candidate_review_packet_v1,
    serialize_ai_coverage_candidate_manifest_v1,
    serialize_ai_coverage_candidate_schema_v1,
)
from evals.structured_nlu.schema import ReviewStatus

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "evals/structured_nlu/data"
SOURCE_DIR = DATA_ROOT / "source"
SPLIT_ASSIGNMENTS = DATA_ROOT / "manifests/split-assignments.v1.json"
CANDIDATE_PATH = REPO_ROOT / "evals/structured_nlu/drafts/coverage-candidates.v1.json"
SCHEMA_PATH = REPO_ROOT / "evals/structured_nlu/ai_coverage_candidate.schema.json"
PACKET_PATH = REPO_ROOT / "evals/structured_nlu/drafts/coverage-review-packet.v1.md"
POLICY_V2_PATH = REPO_ROOT / "evals/structured_nlu/manifests/ai-origin-policy.v2.json"


def test_coverage_candidates_target_the_exact_missing_field_inventory() -> None:
    dataset = compile_authoring_directory(SOURCE_DIR, SPLIT_ASSIGNMENTS)
    report = build_development_coverage_progress(dataset)
    manifest = build_ai_coverage_candidate_manifest_v1()
    missing_fields = {
        (gap.scenario_key, value)
        for gap in report.missing_obligations
        if gap.dimension is CoverageDimension.FIELD_PRESENT
        for value in gap.missing_values
    }
    targets = {(item.scenario_key, item.primary_obligation.value) for item in manifest.suggestions}

    assert manifest.provenance == AI_DRAFT_PROVENANCE
    assert manifest.generator_id == AI_COVERAGE_CANDIDATE_GENERATOR_ID
    assert manifest.human_review_required is True
    assert manifest.automatic_promotion_allowed is False
    assert manifest.baseline_case_count == 36
    assert manifest.baseline_corpus_fingerprint == report.corpus_fingerprint
    assert len(manifest.suggestions) == 24
    assert targets == missing_fields


def test_coverage_candidates_pass_live_semantics_and_only_emit_the_target_field() -> None:
    manifest = build_ai_coverage_candidate_manifest_v1()

    for suggestion in manifest.suggestions:
        proposed = suggestion.proposed_case
        present = {
            name for name, expectation in proposed.labels.fields.items() if expectation is not None
        }
        assert present == {suggestion.target_field}
        if proposed.labels.user_action == "provide_details":
            assert proposed.current_fields[suggestion.target_field] is None
            assert any(value is not None for value in proposed.current_fields.values())
        else:
            assert proposed.labels.user_action == "select_alternative_time"
            selected = proposed.labels.fields["selected_time"]
            assert selected is not None
            assert selected.accepted_values[0] in proposed.offered_alternative_times


def test_coverage_projection_is_233_obligations_without_promoting_candidates() -> None:
    dataset = compile_authoring_directory(SOURCE_DIR, SPLIT_ASSIGNMENTS)
    manifest = build_ai_coverage_candidate_manifest_v1()
    diagnostic_cases = tuple(
        SimpleNamespace(
            id=suggestion.proposed_case.id,
            scenario_key=suggestion.scenario_key,
            conversation_state=suggestion.proposed_case.conversation_state,
            current_fields=suggestion.proposed_case.current_fields,
            offered_alternative_times=suggestion.proposed_case.offered_alternative_times,
            labels=suggestion.proposed_case.labels,
            tags=suggestion.proposed_case.tags,
            review_status=ReviewStatus.DRAFT,
        )
        for suggestion in manifest.suggestions
    )
    before = build_development_coverage_progress(dataset)
    after = build_development_coverage_progress(dataset, diagnostic_cases=diagnostic_cases)

    assert after.covered_obligation_count - before.covered_obligation_count == 233
    assert after.covered_obligation_count == manifest.projected_covered_obligation_count == 582
    assert len(dataset.cases) == 36


def test_coverage_candidate_payload_cannot_be_promoted_or_drifted() -> None:
    payload = json.loads(serialize_ai_coverage_candidate_manifest_v1())
    with pytest.raises(ValidationError):
        AuthoringGroup.model_validate(payload)

    candidate = build_ai_coverage_candidate_manifest_v1().suggestions[0]
    source_payload = {
        "authoring_schema_version": 2,
        "conversation_group_id": "human-renamed-coverage-candidate",
        "scenario_key": candidate.scenario_key,
        "provenance": "human_authored",
        "cases": [
            {
                **candidate.proposed_case.model_dump(mode="json"),
                "id": "human-renamed-coverage-candidate.c1",
                "user_message": unicodedata.normalize("NFD", candidate.proposed_case.user_message),
                "review_status": "draft",
            }
        ],
    }
    with pytest.raises(ValidationError, match="verbatim AI-origin text"):
        AuthoringGroup.model_validate(source_payload)
    historical = AuthoringGroup.model_validate(
        source_payload,
        context={"ai_origin_policy_schema_version": 1},
    )
    assert historical.provenance == "human_authored"
    with pytest.raises(ValidationError, match="unsupported AI-origin policy schema version"):
        AuthoringGroup.model_validate(
            source_payload,
            context={"ai_origin_policy_schema_version": False},
        )

    payload = json.loads(serialize_ai_coverage_candidate_manifest_v1())
    payload["suggestions"][0]["proposed_case"]["user_message"] += " 수정"
    with pytest.raises(ValidationError, match="drifted from the V1 policy"):
        AICoverageCandidateManifestV1.model_validate(payload)


@pytest.mark.parametrize(
    ("path", "invalid_value"),
    [
        (("provenance",), "human_authored"),
        (("suggestions", 0, "proposed_case", "user_message"), "   "),
    ],
)
def test_coverage_candidate_manifest_rejects_invalid_literals_and_blank_text(
    path: tuple[str | int, ...],
    invalid_value: str,
) -> None:
    payload = json.loads(serialize_ai_coverage_candidate_manifest_v1())
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = invalid_value

    with pytest.raises(ValidationError):
        AICoverageCandidateManifestV1.model_validate(payload)


def test_coverage_candidate_manifest_rejects_unknown_proposed_case_fields() -> None:
    payload = json.loads(serialize_ai_coverage_candidate_manifest_v1())
    payload["suggestions"][0]["proposed_case"]["unexpected"] = True

    with pytest.raises(ValidationError):
        AICoverageCandidateManifestV1.model_validate(payload)


def test_coverage_candidate_artifacts_and_ai_origin_v2_are_immutable() -> None:
    assert CANDIDATE_PATH.read_text(encoding="utf-8") == (
        serialize_ai_coverage_candidate_manifest_v1()
    )
    assert SCHEMA_PATH.read_text(encoding="utf-8") == serialize_ai_coverage_candidate_schema_v1()
    assert PACKET_PATH.read_text(encoding="utf-8") == (
        render_ai_coverage_candidate_review_packet_v1()
    )
    assert len(AI_ORIGIN_TEXT_FINGERPRINTS_V2) == 56
    assert ai_origin_policy_fingerprint_v2() == EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V2
    assert POLICY_V2_PATH.read_text(encoding="utf-8") == serialize_ai_origin_policy_v2()


def test_coverage_review_packet_only_requests_approve_edit_or_reject() -> None:
    packet = render_ai_coverage_candidate_review_packet_v1()

    assert packet.count("[ ] 승인  [ ] 수정 필요  [ ] 거부") == 24
    assert "사람이 새로 작성한 발화" not in packet
    assert "자동 승격 허용: `false`" in packet
    assert "커밋된 원본은 직접 체크하지 말고 작업용 사본" in packet


@pytest.mark.parametrize(
    ("write_command", "check_command", "expected"),
    [
        (
            "draft-coverage-candidates",
            "check-draft-coverage-candidates",
            serialize_ai_coverage_candidate_manifest_v1,
        ),
        (
            "draft-coverage-schema",
            "check-draft-coverage-schema",
            serialize_ai_coverage_candidate_schema_v1,
        ),
        (
            "draft-coverage-review-packet",
            "check-draft-coverage-review-packet",
            render_ai_coverage_candidate_review_packet_v1,
        ),
        ("ai-origin-policy-v2", "check-ai-origin-policy-v2", serialize_ai_origin_policy_v2),
    ],
)
def test_coverage_candidate_cli_writes_and_checks_exact_artifacts(
    tmp_path: Path,
    write_command: str,
    check_command: str,
    expected,
) -> None:
    output = tmp_path / f"{write_command}.txt"
    base = [sys.executable, "-m", "scripts.compile_structured_nlu_corpus"]

    subprocess.run([*base, write_command, str(output)], cwd=REPO_ROOT, check=True)
    assert output.read_text(encoding="utf-8") == expected()
    subprocess.run([*base, check_command, str(output)], cwd=REPO_ROOT, check=True)

    output.write_text("{}\n", encoding="utf-8")
    stale = subprocess.run(
        [*base, check_command, str(output)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert stale.returncode != 0
