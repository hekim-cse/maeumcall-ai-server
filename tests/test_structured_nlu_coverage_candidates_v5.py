import hashlib
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.structured_nlu.authoring import compile_authoring_directory
from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.coverage_progress import build_development_coverage_progress
from evals.structured_nlu.drafting import (
    AICoverageCandidateManifestV5,
    build_ai_coverage_candidate_manifest_v1,
    build_ai_coverage_candidate_manifest_v2,
    build_ai_coverage_candidate_manifest_v3,
    build_ai_coverage_candidate_manifest_v4,
    build_ai_coverage_candidate_manifest_v5,
    coverage_candidate_diagnostic_cases,
    render_ai_coverage_candidate_review_packet_v5,
    serialize_ai_coverage_candidate_manifest_v5,
    serialize_ai_coverage_candidate_schema_v5,
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
    )
    v5 = build_ai_coverage_candidate_manifest_v5()
    before = build_development_coverage_progress(
        dataset, diagnostic_cases=coverage_candidate_diagnostic_cases(*previous)
    )
    after = build_development_coverage_progress(
        dataset, diagnostic_cases=coverage_candidate_diagnostic_cases(*previous, v5)
    )
    return dataset, v5, before, after


def test_v5_is_the_exact_remaining_field_option_family() -> None:
    dataset, v5, before, after = _reports()
    targets = {
        (ref.scenario_key, ref.dimension, ref.value)
        for suggestion in v5.suggestions
        for ref in suggestion.target_obligations
    }
    projected = {
        (ref.scenario_key, ref.dimension, ref.value)
        for suggestion in v5.suggestions
        for ref in suggestion.projected_obligations
    }
    missing_options = {key for key in _missing(before) if key[1] is CoverageDimension.FIELD_OPTION}

    assert len(dataset.cases) == 36
    assert len(v5.baseline_diagnostic_case_ids) == 78
    assert targets == missing_options and len(targets) == 53
    assert projected == _missing(before) - _missing(after) and len(projected) == 63
    assert (before.covered_obligation_count, before.missing_obligation_count) == (713, 849)
    assert (after.covered_obligation_count, after.missing_obligation_count) == (776, 786)
    assert CoverageDimension.FIELD_OPTION not in after.missing_dimension_counts


def test_v5_candidate_count_meets_the_structural_lower_bound() -> None:
    _, v5, before, _ = _reports()
    counts_by_scenario_field = defaultdict(lambda: defaultdict(int))
    for scenario, dimension, value in _missing(before):
        if dimension is CoverageDimension.FIELD_OPTION:
            field_name, _ = value.split("=", 1)
            counts_by_scenario_field[scenario][field_name] += 1
    lower_bound = sum(
        max(field_counts.values()) for field_counts in counts_by_scenario_field.values()
    )

    assert lower_bound == 27
    assert len(v5.suggestions) == lower_bound
    for suggestion in v5.suggestions:
        option_fields = dict(EVALUATION_CONTRACTS[suggestion.scenario_key].field_options)
        observed = {
            f"{name}={expected.accepted_values[0]}"
            for name, expected in suggestion.proposed_case.labels.fields.items()
            if expected is not None and name in option_fields
        }
        targeted = {ref.value for ref in suggestion.target_obligations}
        assert targeted <= observed


def test_v5_artifacts_are_deterministic_and_bind_v4() -> None:
    base = ROOT / "evals/structured_nlu"
    assert (base / "drafts/coverage-candidates.v5.json").read_text(
        encoding="utf-8"
    ) == serialize_ai_coverage_candidate_manifest_v5()
    assert (base / "ai_coverage_candidate_v5.schema.json").read_text(
        encoding="utf-8"
    ) == serialize_ai_coverage_candidate_schema_v5()
    assert (base / "drafts/coverage-review-packet.v5.md").read_text(
        encoding="utf-8"
    ) == render_ai_coverage_candidate_review_packet_v5()
    predecessor = base / "drafts/coverage-candidates.v4.json"
    assert hashlib.sha256(predecessor.read_bytes()).hexdigest() == (
        build_ai_coverage_candidate_manifest_v5().predecessor_artifact_sha256
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["suggestions"][0].__setitem__("unexpected", True),
        lambda payload: payload["suggestions"][0]["target_obligations"].pop(),
        lambda payload: payload["suggestions"][0]["proposed_case"].__setitem__("user_message", " "),
        lambda payload: payload.__setitem__("projected_marginal_gain", 62),
    ],
)
def test_v5_rejects_manifest_drift(mutate) -> None:
    payload = build_ai_coverage_candidate_manifest_v5().model_dump(mode="json")
    mutate(payload)
    with pytest.raises(ValidationError):
        AICoverageCandidateManifestV5.model_validate(payload)


def test_v1_through_v4_artifact_bytes_remain_unchanged() -> None:
    expected = {
        "drafts/coverage-candidates.v1.json": "28128c46b3b3a3a559066dd8dfbbf17e95344bc2d58079603a09da0c8fa5f6dc",
        "drafts/coverage-candidates.v2.json": "88c18840f4a35db70b925bde0642a6801a48c501f8db7f1621ae9a193d85ec8a",
        "drafts/coverage-candidates.v3.json": "c30d43ede76fd4db84797be270201b5382eecc7b8fa71a93c2b36d55a0ea8e03",
        "drafts/coverage-candidates.v4.json": "ee19aa48f772c0bd16d8819bf90c0c06c5e4a9426bd4b9d09f74dfe380ee7565",
    }
    base = ROOT / "evals/structured_nlu"
    assert {
        path: hashlib.sha256((base / path).read_bytes()).hexdigest() for path in expected
    } == expected


def test_v5_cli_replays_the_complete_candidate_chain() -> None:
    base = ROOT / "evals/structured_nlu"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.compile_structured_nlu_corpus",
            "check-draft-coverage-candidates-v5",
            str(DATA / "source"),
            str(DATA / "manifests/split-assignments.v1.json"),
            str(base / "drafts/coverage-candidates.v1.json"),
            str(base / "drafts/coverage-candidates.v2.json"),
            str(base / "drafts/coverage-candidates.v3.json"),
            str(base / "drafts/coverage-candidates.v4.json"),
            str(base / "drafts/coverage-candidates.v5.json"),
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
        ("check-draft-coverage-schema-v5", "ai_coverage_candidate_v5.schema.json"),
        (
            "check-draft-coverage-review-packet-v5",
            "drafts/coverage-review-packet.v5.md",
        ),
        ("check-ai-origin-policy-v6", "manifests/ai-origin-policy.v6.json"),
        ("check-ai-origin-policy-schema-v6", "ai_origin_policy.schema.v6.json"),
    ],
)
def test_v5_and_policy_v6_cli_artifact_checks(command: str, relative_path: str) -> None:
    artifact = ROOT / "evals/structured_nlu" / relative_path
    result = subprocess.run(
        [sys.executable, "-m", "scripts.compile_structured_nlu_corpus", command, str(artifact)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
