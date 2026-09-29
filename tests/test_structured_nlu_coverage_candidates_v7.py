import hashlib
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.structured_nlu.authoring import compile_authoring_directory
from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.coverage_progress import build_development_coverage_progress
from evals.structured_nlu.drafting import (
    AICoverageCandidateManifestV7,
    build_ai_coverage_candidate_manifest_v1,
    build_ai_coverage_candidate_manifest_v2,
    build_ai_coverage_candidate_manifest_v3,
    build_ai_coverage_candidate_manifest_v4,
    build_ai_coverage_candidate_manifest_v5,
    build_ai_coverage_candidate_manifest_v6,
    build_ai_coverage_candidate_manifest_v7,
    coverage_candidate_diagnostic_cases,
    render_ai_coverage_candidate_review_packet_v7,
    serialize_ai_coverage_candidate_manifest_v7,
    serialize_ai_coverage_candidate_schema_v7,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "evals/structured_nlu"
DATA = BASE / "data"


def _missing(report):
    return {
        (gap.scenario_key, gap.dimension, value)
        for gap in report.missing_obligations
        for value in gap.missing_values
    }


def _reports():
    dataset = compile_authoring_directory(
        DATA / "source",
        DATA / "manifests/split-assignments.v1.json",
    )
    previous = (
        build_ai_coverage_candidate_manifest_v1(),
        build_ai_coverage_candidate_manifest_v2(),
        build_ai_coverage_candidate_manifest_v3(),
        build_ai_coverage_candidate_manifest_v4(),
        build_ai_coverage_candidate_manifest_v5(),
        build_ai_coverage_candidate_manifest_v6(),
    )
    v7 = build_ai_coverage_candidate_manifest_v7()
    before = build_development_coverage_progress(
        dataset, diagnostic_cases=coverage_candidate_diagnostic_cases(*previous)
    )
    after = build_development_coverage_progress(
        dataset, diagnostic_cases=coverage_candidate_diagnostic_cases(*previous, v7)
    )
    return dataset, v7, before, after


def test_v7_is_the_exact_remaining_action_field_present_family() -> None:
    dataset, v7, before, after = _reports()
    targets = {
        (ref.scenario_key, ref.dimension, ref.value)
        for suggestion in v7.suggestions
        for ref in suggestion.target_obligations
    }
    projected = {
        (ref.scenario_key, ref.dimension, ref.value)
        for suggestion in v7.suggestions
        for ref in suggestion.projected_obligations
    }
    missing_targets = {
        key for key in _missing(before) if key[1] is CoverageDimension.ACTION_FIELD_PRESENT
    }

    assert len(dataset.cases) == 36
    assert len(v7.baseline_diagnostic_case_ids) == 143
    assert targets == missing_targets and len(targets) == 28
    assert projected == _missing(before) - _missing(after) and len(projected) == 59
    assert (before.covered_obligation_count, before.missing_obligation_count) == (900, 662)
    assert (after.covered_obligation_count, after.missing_obligation_count) == (959, 603)
    assert CoverageDimension.ACTION_FIELD_PRESENT not in after.missing_dimension_counts


def test_v7_meets_the_live_action_field_structural_lower_bound() -> None:
    _, v7, before, _ = _reports()
    missing_by_action = Counter()
    for scenario, dimension, value in _missing(before):
        if dimension is CoverageDimension.ACTION_FIELD_PRESENT:
            action, _ = value.split("->", 1)
            missing_by_action[scenario, action] += 1
    # Only assignment ask_follow_up can carry its two remaining fields together.
    lower_bound = sum(
        1 if count == 2 and action == "ask_follow_up" else count
        for (_, action), count in missing_by_action.items()
    )

    assert lower_bound == 27
    assert len(v7.suggestions) == lower_bound
    assert sorted(len(item.target_obligations) for item in v7.suggestions).count(2) == 1
    assert sum(len(item.target_obligations) for item in v7.suggestions) == 28


def test_v7_artifacts_are_deterministic_and_bind_v6() -> None:
    assert (BASE / "drafts/coverage-candidates.v7.json").read_text(
        encoding="utf-8"
    ) == serialize_ai_coverage_candidate_manifest_v7()
    assert (BASE / "ai_coverage_candidate_v7.schema.json").read_text(
        encoding="utf-8"
    ) == serialize_ai_coverage_candidate_schema_v7()
    assert (BASE / "drafts/coverage-review-packet.v7.md").read_text(
        encoding="utf-8"
    ) == render_ai_coverage_candidate_review_packet_v7()
    assert hashlib.sha256(
        (BASE / "drafts/coverage-candidates.v6.json").read_bytes()
    ).hexdigest() == (build_ai_coverage_candidate_manifest_v7().predecessor_artifact_sha256)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["suggestions"][0].__setitem__("unexpected", True),
        lambda payload: payload["suggestions"][0]["target_obligations"].pop(),
        lambda payload: payload["suggestions"][0]["proposed_case"]["labels"].__setitem__(
            "user_action", "unknown"
        ),
        lambda payload: payload.__setitem__("projected_marginal_gain", 58),
    ],
)
def test_v7_rejects_manifest_drift(mutate) -> None:
    payload = build_ai_coverage_candidate_manifest_v7().model_dump(mode="json")
    mutate(payload)
    with pytest.raises(ValidationError):
        AICoverageCandidateManifestV7.model_validate(payload)


def test_v1_through_v6_candidate_artifact_bytes_remain_unchanged() -> None:
    expected = {
        1: "28128c46b3b3a3a559066dd8dfbbf17e95344bc2d58079603a09da0c8fa5f6dc",
        2: "88c18840f4a35db70b925bde0642a6801a48c501f8db7f1621ae9a193d85ec8a",
        3: "c30d43ede76fd4db84797be270201b5382eecc7b8fa71a93c2b36d55a0ea8e03",
        4: "ee19aa48f772c0bd16d8819bf90c0c06c5e4a9426bd4b9d09f74dfe380ee7565",
        5: "4865192fcd1f662ffca533035f99f9f9b0ae6a2cb675b62278ab0358385434c5",
        6: "70c8e8d6c3000d58d361d03effdd66c4d7833be9a31c09ebda75886ca6834630",
    }
    assert {
        version: hashlib.sha256(
            (BASE / f"drafts/coverage-candidates.v{version}.json").read_bytes()
        ).hexdigest()
        for version in expected
    } == expected


def test_v7_cli_replays_the_complete_candidate_chain() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.compile_structured_nlu_corpus",
            "check-draft-coverage-candidates-v7",
            str(DATA / "source"),
            str(DATA / "manifests/split-assignments.v1.json"),
            *(str(BASE / f"drafts/coverage-candidates.v{version}.json") for version in range(1, 8)),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("command", "committed"),
    [
        ("draft-coverage-candidates-v7", "drafts/coverage-candidates.v7.json"),
        ("draft-coverage-schema-v7", "ai_coverage_candidate_v7.schema.json"),
        ("draft-coverage-review-packet-v7", "drafts/coverage-review-packet.v7.md"),
    ],
)
def test_v7_cli_generation_is_create_only(tmp_path: Path, command: str, committed: str) -> None:
    output = tmp_path / Path(committed).name
    first = subprocess.run(
        [sys.executable, "-m", "scripts.compile_structured_nlu_corpus", command, str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    second = subprocess.run(
        [sys.executable, "-m", "scripts.compile_structured_nlu_corpus", command, str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert first.returncode == 0, first.stderr
    assert output.read_bytes() == (BASE / committed).read_bytes()
    assert second.returncode != 0
    assert "already exists" in second.stderr


@pytest.mark.parametrize(
    ("command", "relative_path"),
    [
        ("check-draft-coverage-schema-v7", "ai_coverage_candidate_v7.schema.json"),
        ("check-draft-coverage-review-packet-v7", "drafts/coverage-review-packet.v7.md"),
    ],
)
def test_v7_cli_artifact_checks(command: str, relative_path: str) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.compile_structured_nlu_corpus",
            command,
            str(BASE / relative_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
