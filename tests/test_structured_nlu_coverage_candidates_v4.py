import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from evals.structured_nlu.authoring import compile_authoring_directory
from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.coverage_progress import build_development_coverage_progress
from evals.structured_nlu.drafting import (
    AICoverageCandidateManifestV4,
    build_ai_coverage_candidate_manifest_v1,
    build_ai_coverage_candidate_manifest_v2,
    build_ai_coverage_candidate_manifest_v3,
    build_ai_coverage_candidate_manifest_v4,
    render_ai_coverage_candidate_review_packet_v4,
    serialize_ai_coverage_candidate_manifest_v4,
    serialize_ai_coverage_candidate_schema_v4,
)
from evals.structured_nlu.schema import ReviewStatus

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data"
V1_MANIFEST = ROOT / "evals/structured_nlu/drafts/coverage-candidates.v1.json"
V2_MANIFEST = ROOT / "evals/structured_nlu/drafts/coverage-candidates.v2.json"
V3_MANIFEST = ROOT / "evals/structured_nlu/drafts/coverage-candidates.v3.json"
V4_MANIFEST = ROOT / "evals/structured_nlu/drafts/coverage-candidates.v4.json"


def _cases(*manifests):
    return tuple(
        SimpleNamespace(
            id=s.proposed_case.id,
            scenario_key=s.scenario_key,
            conversation_state=s.proposed_case.conversation_state,
            current_fields=s.proposed_case.current_fields,
            offered_alternative_times=s.proposed_case.offered_alternative_times,
            labels=s.proposed_case.labels,
            tags=s.proposed_case.tags,
            review_status=ReviewStatus.DRAFT,
        )
        for m in manifests
        for s in m.suggestions
    )


def _missing(report):
    return {
        (g.scenario_key, g.dimension, value)
        for g in report.missing_obligations
        for value in g.missing_values
    }


def test_v4_exact_targets_and_projection() -> None:
    dataset = compile_authoring_directory(
        ROOT / "evals/structured_nlu/data/source",
        ROOT / "evals/structured_nlu/data/manifests/split-assignments.v1.json",
    )
    manifests = (
        build_ai_coverage_candidate_manifest_v1(),
        build_ai_coverage_candidate_manifest_v2(),
        build_ai_coverage_candidate_manifest_v3(),
    )
    v4 = build_ai_coverage_candidate_manifest_v4()
    before = build_development_coverage_progress(dataset, diagnostic_cases=_cases(*manifests))
    after = build_development_coverage_progress(dataset, diagnostic_cases=_cases(*manifests, v4))
    missing_options = {
        key for key in _missing(before) if key[1] is CoverageDimension.CURRENT_FIELD_OPTION
    }
    targets = {
        (r.scenario_key, r.dimension, r.value) for s in v4.suggestions for r in s.target_obligations
    }
    projected = {
        (r.scenario_key, r.dimension, r.value)
        for s in v4.suggestions
        for r in s.projected_obligations
    }
    assert len(v4.suggestions) == 19
    assert targets == missing_options and len(targets) == 34
    assert projected == _missing(before) - _missing(after) and len(projected) == 45
    assert (before.covered_obligation_count, before.missing_obligation_count) == (668, 894)
    assert (after.covered_obligation_count, after.missing_obligation_count) == (713, 849)
    assert CoverageDimension.CURRENT_FIELD_OPTION not in after.missing_dimension_counts
    assert len(dataset.cases) == 36


def test_v4_non_null_current_options_are_exactly_declared_targets() -> None:
    for suggestion in build_ai_coverage_candidate_manifest_v4().suggestions:
        observed = {
            f"{name}={value}"
            for name, value in suggestion.proposed_case.current_fields.items()
            if value is not None
        }
        declared = {ref.value for ref in suggestion.target_obligations}
        assert observed == declared
        assert all(value is None for value in suggestion.proposed_case.labels.fields.values())
        assert suggestion.proposed_case.labels.user_action == "unknown"


def test_v4_rejects_cross_batch_conversation_group_id() -> None:
    payload = build_ai_coverage_candidate_manifest_v4().model_dump(mode="json")
    payload["suggestions"][0]["conversation_group_id"] = (
        "ai-coverage-v3-hair-salon-unavailable-ask-other-time-no-offers"
    )
    with pytest.raises(ValidationError, match="globally unique"):
        AICoverageCandidateManifestV4.model_validate(payload)


def test_v4_artifacts_are_deterministic() -> None:
    base = ROOT / "evals/structured_nlu"
    assert (
        base / "drafts/coverage-candidates.v4.json"
    ).read_text() == serialize_ai_coverage_candidate_manifest_v4()
    assert (
        base / "ai_coverage_candidate_v4.schema.json"
    ).read_text() == serialize_ai_coverage_candidate_schema_v4()
    assert (
        base / "drafts/coverage-review-packet.v4.md"
    ).read_text() == render_ai_coverage_candidate_review_packet_v4()
    assert (
        build_ai_coverage_candidate_manifest_v4().predecessor_artifact_sha256
        == "c30d43ede76fd4db84797be270201b5382eecc7b8fa71a93c2b36d55a0ea8e03"
    )


def test_v4_cli_replays_the_complete_candidate_chain() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.compile_structured_nlu_corpus",
            "check-draft-coverage-candidates-v4",
            str(DATA / "source"),
            str(DATA / "manifests/split-assignments.v1.json"),
            str(V1_MANIFEST),
            str(V2_MANIFEST),
            str(V3_MANIFEST),
            str(V4_MANIFEST),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_v4_and_policy_v5_cli_checks_match_committed_artifacts() -> None:
    checks = (
        (
            "check-draft-coverage-schema-v4",
            ROOT / "evals/structured_nlu/ai_coverage_candidate_v4.schema.json",
        ),
        (
            "check-draft-coverage-review-packet-v4",
            ROOT / "evals/structured_nlu/drafts/coverage-review-packet.v4.md",
        ),
        (
            "check-ai-origin-policy-v5",
            ROOT / "evals/structured_nlu/manifests/ai-origin-policy.v5.json",
        ),
        (
            "check-ai-origin-policy-schema-v5",
            ROOT / "evals/structured_nlu/ai_origin_policy.schema.v5.json",
        ),
    )
    for command, artifact in checks:
        result = subprocess.run(
            [sys.executable, "-m", "scripts.compile_structured_nlu_corpus", command, str(artifact)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
