import hashlib
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.structured_nlu.authoring import compile_authoring_directory
from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.coverage_progress import build_development_coverage_progress
from evals.structured_nlu.drafting import (
    AICoverageCandidateManifestV6,
    build_ai_coverage_candidate_manifest_v1,
    build_ai_coverage_candidate_manifest_v2,
    build_ai_coverage_candidate_manifest_v3,
    build_ai_coverage_candidate_manifest_v4,
    build_ai_coverage_candidate_manifest_v5,
    build_ai_coverage_candidate_manifest_v6,
    coverage_candidate_diagnostic_cases,
    render_ai_coverage_candidate_review_packet_v6,
    serialize_ai_coverage_candidate_manifest_v6,
    serialize_ai_coverage_candidate_schema_v6,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data"


def _missing(report):
    return {
        (gap.scenario_key, gap.dimension, value)
        for gap in report.missing_obligations
        for value in gap.missing_values
    }


def _reports():
    dataset = compile_authoring_directory(
        ROOT / "evals/structured_nlu/data/source",
        ROOT / "evals/structured_nlu/data/manifests/split-assignments.v1.json",
    )
    previous = (
        build_ai_coverage_candidate_manifest_v1(),
        build_ai_coverage_candidate_manifest_v2(),
        build_ai_coverage_candidate_manifest_v3(),
        build_ai_coverage_candidate_manifest_v4(),
        build_ai_coverage_candidate_manifest_v5(),
    )
    v6 = build_ai_coverage_candidate_manifest_v6()
    before = build_development_coverage_progress(
        dataset, diagnostic_cases=coverage_candidate_diagnostic_cases(*previous)
    )
    after = build_development_coverage_progress(
        dataset, diagnostic_cases=coverage_candidate_diagnostic_cases(*previous, v6)
    )
    return dataset, v6, before, after


def test_v6_is_the_exact_remaining_change_field_family() -> None:
    dataset, v6, before, after = _reports()
    targets = {
        (ref.scenario_key, ref.dimension, ref.value)
        for suggestion in v6.suggestions
        for ref in suggestion.target_obligations
    }
    projected = {
        (ref.scenario_key, ref.dimension, ref.value)
        for suggestion in v6.suggestions
        for ref in suggestion.projected_obligations
    }
    missing_change_fields = {
        key for key in _missing(before) if key[1] is CoverageDimension.CHANGE_FIELD
    }

    assert len(dataset.cases) == 36
    assert len(v6.baseline_diagnostic_case_ids) == 105
    assert targets == missing_change_fields and len(targets) == 38
    assert projected == _missing(before) - _missing(after) and len(projected) == 124
    assert (before.covered_obligation_count, before.missing_obligation_count) == (776, 786)
    assert (after.covered_obligation_count, after.missing_obligation_count) == (900, 662)
    assert CoverageDimension.CHANGE_FIELD not in after.missing_dimension_counts


def test_v6_meets_the_one_change_field_per_case_lower_bound() -> None:
    _, v6, before, _ = _reports()
    lower_bound = sum(
        len(gap.missing_values)
        for gap in before.missing_obligations
        if gap.dimension is CoverageDimension.CHANGE_FIELD
    )

    assert lower_bound == 38
    assert len(v6.suggestions) == lower_bound
    for suggestion in v6.suggestions:
        proposed = suggestion.proposed_case
        present = {
            name for name, expected in proposed.labels.fields.items() if expected is not None
        }
        assert proposed.labels.user_action == "change_detail"
        assert present == {proposed.labels.change_field}
        assert proposed.current_fields[proposed.labels.change_field] is not None
        assert len(suggestion.target_obligations) == 1


def test_v6_artifacts_are_deterministic_and_bind_v5() -> None:
    base = ROOT / "evals/structured_nlu"
    assert (base / "drafts/coverage-candidates.v6.json").read_text(
        encoding="utf-8"
    ) == serialize_ai_coverage_candidate_manifest_v6()
    assert (base / "ai_coverage_candidate_v6.schema.json").read_text(
        encoding="utf-8"
    ) == serialize_ai_coverage_candidate_schema_v6()
    assert (base / "drafts/coverage-review-packet.v6.md").read_text(
        encoding="utf-8"
    ) == render_ai_coverage_candidate_review_packet_v6()
    predecessor = base / "drafts/coverage-candidates.v5.json"
    assert hashlib.sha256(predecessor.read_bytes()).hexdigest() == (
        build_ai_coverage_candidate_manifest_v6().predecessor_artifact_sha256
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["suggestions"][0].__setitem__("unexpected", True),
        lambda payload: payload["suggestions"][0]["target_obligations"].pop(),
        lambda payload: payload["suggestions"][0]["proposed_case"]["labels"].__setitem__(
            "change_field", "not_a_field"
        ),
        lambda payload: payload.__setitem__("projected_marginal_gain", 123),
    ],
)
def test_v6_rejects_manifest_drift(mutate) -> None:
    payload = build_ai_coverage_candidate_manifest_v6().model_dump(mode="json")
    mutate(payload)
    with pytest.raises(ValidationError):
        AICoverageCandidateManifestV6.model_validate(payload)


def test_v1_through_v5_candidate_artifact_bytes_remain_unchanged() -> None:
    expected = {
        "coverage-candidates.v1.json": "28128c46b3b3a3a559066dd8dfbbf17e95344bc2d58079603a09da0c8fa5f6dc",
        "coverage-candidates.v2.json": "88c18840f4a35db70b925bde0642a6801a48c501f8db7f1621ae9a193d85ec8a",
        "coverage-candidates.v3.json": "c30d43ede76fd4db84797be270201b5382eecc7b8fa71a93c2b36d55a0ea8e03",
        "coverage-candidates.v4.json": "ee19aa48f772c0bd16d8819bf90c0c06c5e4a9426bd4b9d09f74dfe380ee7565",
        "coverage-candidates.v5.json": "4865192fcd1f662ffca533035f99f9f9b0ae6a2cb675b62278ab0358385434c5",
    }
    base = ROOT / "evals/structured_nlu/drafts"
    assert {
        name: hashlib.sha256((base / name).read_bytes()).hexdigest() for name in expected
    } == expected


def test_v6_cli_replays_the_complete_candidate_chain() -> None:
    base = ROOT / "evals/structured_nlu"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.compile_structured_nlu_corpus",
            "check-draft-coverage-candidates-v6",
            str(DATA / "source"),
            str(DATA / "manifests/split-assignments.v1.json"),
            *(str(base / f"drafts/coverage-candidates.v{version}.json") for version in range(1, 7)),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("command", "relative_path"),
    [
        ("check-draft-coverage-schema-v6", "ai_coverage_candidate_v6.schema.json"),
        (
            "check-draft-coverage-review-packet-v6",
            "drafts/coverage-review-packet.v6.md",
        ),
        ("check-ai-origin-policy-v7", "manifests/ai-origin-policy.v7.json"),
        ("check-ai-origin-policy-schema-v7", "ai_origin_policy.schema.v7.json"),
    ],
)
def test_v6_and_policy_v7_cli_artifact_checks(command: str, relative_path: str) -> None:
    artifact = ROOT / "evals/structured_nlu" / relative_path
    result = subprocess.run(
        [sys.executable, "-m", "scripts.compile_structured_nlu_corpus", command, str(artifact)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
