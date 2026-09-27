from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from evals.structured_nlu.authoring import AuthoringGroup, compile_authoring_directory
from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.coverage_progress import build_development_coverage_progress
from evals.structured_nlu.coverage_v3 import classify_alternative_time_relation
from evals.structured_nlu.drafting import (
    AICoverageCandidateManifestV3,
    build_ai_coverage_candidate_manifest_v1,
    build_ai_coverage_candidate_manifest_v2,
    build_ai_coverage_candidate_manifest_v3,
    render_ai_coverage_candidate_review_packet_v3,
    serialize_ai_coverage_candidate_manifest_v1,
    serialize_ai_coverage_candidate_manifest_v2,
    serialize_ai_coverage_candidate_manifest_v3,
    serialize_ai_coverage_candidate_schema_v1,
    serialize_ai_coverage_candidate_schema_v2,
    serialize_ai_coverage_candidate_schema_v3,
)
from evals.structured_nlu.schema import ReviewStatus

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data"
V1_MANIFEST = ROOT / "evals/structured_nlu/drafts/coverage-candidates.v1.json"
V2_MANIFEST = ROOT / "evals/structured_nlu/drafts/coverage-candidates.v2.json"
V3_MANIFEST = ROOT / "evals/structured_nlu/drafts/coverage-candidates.v3.json"
V3_SCHEMA = ROOT / "evals/structured_nlu/ai_coverage_candidate_v3.schema.json"
V3_PACKET = ROOT / "evals/structured_nlu/drafts/coverage-review-packet.v3.md"


def _diagnostics(*manifests):
    return tuple(
        SimpleNamespace(
            id=item.proposed_case.id,
            scenario_key=item.scenario_key,
            conversation_state=item.proposed_case.conversation_state,
            current_fields=item.proposed_case.current_fields,
            offered_alternative_times=item.proposed_case.offered_alternative_times,
            labels=item.proposed_case.labels,
            tags=item.proposed_case.tags,
            review_status=ReviewStatus.DRAFT,
        )
        for manifest in manifests
        for item in manifest.suggestions
    )


def _missing(report):
    return {
        (gap.scenario_key, gap.dimension, value)
        for gap in report.missing_obligations
        for value in gap.missing_values
    }


def test_v3_targets_the_exact_remaining_alternative_relation_family() -> None:
    dataset = compile_authoring_directory(
        DATA / "source", DATA / "manifests/split-assignments.v1.json"
    )
    v1 = build_ai_coverage_candidate_manifest_v1()
    v2 = build_ai_coverage_candidate_manifest_v2()
    v3 = build_ai_coverage_candidate_manifest_v3()
    baseline = build_development_coverage_progress(dataset, diagnostic_cases=_diagnostics(v1, v2))
    missing = {
        key for key in _missing(baseline) if key[1] is CoverageDimension.ALTERNATIVE_TIME_RELATION
    }
    primary = {
        (item.scenario_key, item.primary_obligation.dimension, item.primary_obligation.value)
        for item in v3.suggestions
    }

    assert (baseline.covered_obligation_count, baseline.missing_obligation_count) == (613, 949)
    assert primary == missing
    assert len(primary) == len(v3.suggestions) == 31


def test_v3_cases_have_exact_relation_labels_and_live_validity() -> None:
    manifest = build_ai_coverage_candidate_manifest_v3()
    messages = {item.proposed_case.user_message for item in manifest.suggestions}

    assert len(messages) == 31
    for item in manifest.suggestions:
        case = item.proposed_case
        selected = case.labels.fields.get("selected_time")
        selected_value = None if selected is None else selected.accepted_values[0]
        relation = classify_alternative_time_relation(
            offered_alternative_times=case.offered_alternative_times,
            selected_time=selected_value,
        )
        assert relation.value == item.relation
        assert case.current_fields == {}
        assert item.semantic_valid is True


def test_v3_projection_is_exact_55_and_completes_the_dimension() -> None:
    dataset = compile_authoring_directory(
        DATA / "source", DATA / "manifests/split-assignments.v1.json"
    )
    v1 = build_ai_coverage_candidate_manifest_v1()
    v2 = build_ai_coverage_candidate_manifest_v2()
    v3 = build_ai_coverage_candidate_manifest_v3()
    before = build_development_coverage_progress(dataset, diagnostic_cases=_diagnostics(v1, v2))
    after = build_development_coverage_progress(dataset, diagnostic_cases=_diagnostics(v1, v2, v3))
    gained = _missing(before) - _missing(after)
    declared = {
        (item.scenario_key, ref.dimension, ref.value)
        for item in v3.suggestions
        for ref in item.projected_obligations
    }

    assert gained == declared
    assert len(gained) == v3.projected_marginal_gain == 55
    assert (after.covered_obligation_count, after.missing_obligation_count) == (668, 894)
    assert not any(
        gap.dimension is CoverageDimension.ALTERNATIVE_TIME_RELATION
        for gap in after.missing_obligations
    )
    gains_by_dimension = {}
    for dimension in before.missing_dimension_counts:
        gain = before.missing_dimension_counts[dimension] - after.missing_dimension_counts.get(
            dimension, 0
        )
        if gain:
            gains_by_dimension[dimension] = gain
    assert gains_by_dimension == {
        CoverageDimension.ACTION_FIELD_PRESENT: 4,
        CoverageDimension.ALTERNATIVE_TIME_RELATION: 31,
        CoverageDimension.SCENARIO_DIFFICULTY_TAG: 4,
        CoverageDimension.STATE_ACTION: 16,
    }
    assert len(dataset.cases) == 36


def test_v3_artifacts_are_deterministic_and_v1_v2_stay_unchanged() -> None:
    pairs = (
        ("drafts/coverage-candidates.v1.json", serialize_ai_coverage_candidate_manifest_v1()),
        ("drafts/coverage-candidates.v2.json", serialize_ai_coverage_candidate_manifest_v2()),
        ("drafts/coverage-candidates.v3.json", serialize_ai_coverage_candidate_manifest_v3()),
        ("ai_coverage_candidate.schema.json", serialize_ai_coverage_candidate_schema_v1()),
        ("ai_coverage_candidate_v2.schema.json", serialize_ai_coverage_candidate_schema_v2()),
        ("ai_coverage_candidate_v3.schema.json", serialize_ai_coverage_candidate_schema_v3()),
        ("drafts/coverage-review-packet.v3.md", render_ai_coverage_candidate_review_packet_v3()),
    )
    for relative, expected in pairs:
        assert (ROOT / "evals/structured_nlu" / relative).read_text(encoding="utf-8") == expected


def test_v3_payload_cannot_be_promoted_or_drifted() -> None:
    payload = json.loads(serialize_ai_coverage_candidate_manifest_v3())
    with pytest.raises(ValidationError):
        AuthoringGroup.model_validate(payload)
    payload["suggestions"][0]["proposed_case"]["user_message"] += " 수정"
    with pytest.raises(ValidationError, match="drifted from policy"):
        AICoverageCandidateManifestV3.model_validate(payload)


def test_v3_review_packet_is_explicitly_unqualified() -> None:
    packet = render_ai_coverage_candidate_review_packet_v3()
    assert packet.count("[ ] 승인  [ ] 수정 필요  [ ] 거부") == 31
    assert "자동 승격 허용: `false`" in packet
    assert "투영 증가: `55`" in packet
    assert "human_authored로 표시할 수 없습니다" in packet


def test_v3_cli_replays_the_complete_candidate_chain() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.compile_structured_nlu_corpus",
            "check-draft-coverage-candidates-v3",
            str(DATA / "source"),
            str(DATA / "manifests/split-assignments.v1.json"),
            str(V1_MANIFEST),
            str(V2_MANIFEST),
            str(V3_MANIFEST),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("command", "artifact"),
    [
        ("check-draft-coverage-schema-v3", V3_SCHEMA),
        ("check-draft-coverage-review-packet-v3", V3_PACKET),
        (
            "check-ai-origin-policy-v4",
            ROOT / "evals/structured_nlu/manifests/ai-origin-policy.v4.json",
        ),
        (
            "check-ai-origin-policy-schema-v4",
            ROOT / "evals/structured_nlu/ai_origin_policy.schema.v4.json",
        ),
    ],
)
def test_v3_and_policy_v4_cli_checks_match_committed_artifacts(
    command: str,
    artifact: Path,
) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "scripts.compile_structured_nlu_corpus", command, str(artifact)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_v3_chain_rejects_a_tampered_predecessor(tmp_path: Path) -> None:
    tampered = tmp_path / "coverage-candidates.v2.json"
    tampered.write_text("{}\n", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.compile_structured_nlu_corpus",
            "check-draft-coverage-candidates-v3",
            str(DATA / "source"),
            str(DATA / "manifests/split-assignments.v1.json"),
            str(V1_MANIFEST),
            str(tampered),
            str(V3_MANIFEST),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "V2 predecessor manifest fingerprint differs" in result.stderr
