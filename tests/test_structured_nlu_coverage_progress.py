import subprocess
import sys
from pathlib import Path

import pytest

from evals.structured_nlu.authoring import compile_authoring_directory
from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.coverage_progress import (
    COVERAGE_PROGRESS_QUALIFICATION,
    CoverageProgressGapV1,
    build_development_coverage_progress,
    serialize_development_coverage_progress,
)
from evals.structured_nlu.obligations import build_official_authoring_obligations
from evals.structured_nlu.schema import DifficultyTag, EvaluationCase, ReviewStatus

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "evals/structured_nlu/data"
SOURCE_DIR = DATA_ROOT / "source"
SPLIT_ASSIGNMENTS_PATH = DATA_ROOT / "manifests/split-assignments.v1.json"
PROGRESS_PATH = DATA_ROOT / "manifests/development-coverage-progress.v1.json"


def test_development_coverage_progress_is_explicitly_unqualified() -> None:
    dataset = compile_authoring_directory(SOURCE_DIR, SPLIT_ASSIGNMENTS_PATH)
    report = build_development_coverage_progress(dataset)

    assert report.qualification_status == COVERAGE_PROGRESS_QUALIFICATION
    assert report.case_count == 36
    assert report.review_status_counts == {ReviewStatus.DRAFT: 36}
    assert report.required_obligation_count == 1_562
    assert report.covered_obligation_count == 349
    assert report.missing_obligation_count == 1_213
    assert report.covered_obligation_count + report.missing_obligation_count == 1_562
    assert report.missing_dimension_counts == {
        CoverageDimension.ACTION_FIELD_ABSENT: 68,
        CoverageDimension.ACTION_FIELD_PRESENT: 94,
        CoverageDimension.ALTERNATIVE_TIME_RELATION: 35,
        CoverageDimension.CHANGE_FIELD: 42,
        CoverageDimension.CONTRAST_ROLE: 75,
        CoverageDimension.CURRENT_DELTA_RELATION: 146,
        CoverageDimension.CURRENT_FIELD_OPTION: 76,
        CoverageDimension.CURRENT_FIELD_PRESENT: 42,
        CoverageDimension.CURRENT_FIELDS_CONTEXT: 103,
        CoverageDimension.FIELD_OPTION: 66,
        CoverageDimension.FIELD_PRESENT: 24,
        CoverageDimension.SCENARIO_DIFFICULTY_TAG: 135,
        CoverageDimension.STATE_ACTION: 307,
    }


def test_progress_manifest_matches_the_current_36_case_sources() -> None:
    dataset = compile_authoring_directory(SOURCE_DIR, SPLIT_ASSIGNMENTS_PATH)

    assert PROGRESS_PATH.read_text(encoding="utf-8") == (
        serialize_development_coverage_progress(dataset)
    )


def test_missing_inventory_keeps_contrast_and_next_field_targets_visible() -> None:
    dataset = compile_authoring_directory(SOURCE_DIR, SPLIT_ASSIGNMENTS_PATH)
    report = build_development_coverage_progress(dataset)
    missing = {
        (gap.scenario_key, gap.dimension, value)
        for gap in report.missing_obligations
        for value in gap.missing_values
    }

    assert (
        "예약:병원 예약",
        CoverageDimension.FIELD_PRESENT,
        "selected_time",
    ) in missing
    assert (
        "고객센터:a/s 접수",
        CoverageDimension.FIELD_PRESENT,
        "model_name",
    ) in missing
    assert (
        sum(
            len(gap.missing_values)
            for gap in report.missing_obligations
            if gap.dimension is CoverageDimension.CONTRAST_ROLE
        )
        == 75
    )


def test_missing_scenario_marks_all_of_its_obligations_missing() -> None:
    dataset = compile_authoring_directory(SOURCE_DIR, SPLIT_ASSIGNMENTS_PATH)
    scenario_key = "고객센터:a/s 접수"
    reduced = dataset.model_copy(
        update={"cases": tuple(case for case in dataset.cases if case.scenario_key != scenario_key)}
    )

    report = build_development_coverage_progress(reduced)
    missing = {
        (gap.scenario_key, gap.dimension, value)
        for gap in report.missing_obligations
        for value in gap.missing_values
    }
    expected = {
        (item.scenario_key, item.dimension, item.value)
        for item in build_official_authoring_obligations()
        if item.scenario_key == scenario_key
    }

    assert expected <= missing


def test_coverage_progress_cli_writes_checks_and_rejects_unsafe_outputs(tmp_path: Path) -> None:
    output = tmp_path / "progress.json"
    base = [sys.executable, "-m", "scripts.compile_structured_nlu_corpus"]
    source_args = [str(SOURCE_DIR), str(SPLIT_ASSIGNMENTS_PATH)]

    subprocess.run(
        [*base, "coverage-progress", *source_args, str(output)],
        cwd=REPO_ROOT,
        check=True,
    )
    subprocess.run(
        [*base, "check-coverage-progress", *source_args, str(output)],
        cwd=REPO_ROOT,
        check=True,
    )
    output.write_text("{}\n", encoding="utf-8")
    stale = subprocess.run(
        [*base, "check-coverage-progress", *source_args, str(output)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert stale.returncode != 0
    assert "differs from the authoring sources" in stale.stderr

    unsafe_source_output = SOURCE_DIR / "coverage-progress.json"
    unsafe = subprocess.run(
        [*base, "coverage-progress", *source_args, str(unsafe_source_output)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert unsafe.returncode != 0
    assert not unsafe_source_output.exists()

    manifest_before = SPLIT_ASSIGNMENTS_PATH.read_bytes()
    manifest_alias = subprocess.run(
        [*base, "coverage-progress", *source_args, str(SPLIT_ASSIGNMENTS_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert manifest_alias.returncode != 0
    assert SPLIT_ASSIGNMENTS_PATH.read_bytes() == manifest_before


def test_only_adjudicated_semantic_tags_increase_progress() -> None:
    dataset = compile_authoring_directory(SOURCE_DIR, SPLIT_ASSIGNMENTS_PATH)
    case = next(item for item in dataset.cases if item.tags == (DifficultyTag.HARD_NEGATIVE,))
    relabelled = EvaluationCase.model_validate(
        {
            **case.model_dump(mode="json"),
            "tags": [
                DifficultyTag.HARD_NEGATIVE,
                DifficultyTag.AMBIGUOUS,
                DifficultyTag.COLLOQUIAL,
                DifficultyTag.ELLIPSIS,
                DifficultyTag.NEGATION,
            ],
        }
    )
    changed = dataset.model_copy(
        update={
            "cases": tuple(relabelled if item.id == case.id else item for item in dataset.cases)
        }
    )

    assert build_development_coverage_progress(changed).covered_obligation_count == 349

    adjudicated = relabelled.model_copy(update={"review_status": ReviewStatus.ADJUDICATED})
    changed = dataset.model_copy(
        update={
            "cases": tuple(adjudicated if item.id == case.id else item for item in dataset.cases)
        }
    )

    assert build_development_coverage_progress(changed).covered_obligation_count == 353


def test_progress_model_rejects_self_inconsistent_counts() -> None:
    dataset = compile_authoring_directory(SOURCE_DIR, SPLIT_ASSIGNMENTS_PATH)
    report = build_development_coverage_progress(dataset)
    payload = report.model_dump(mode="json")
    payload["case_count"] = 500

    with pytest.raises(ValueError, match="review status counts"):
        type(report).model_validate(payload)

    payload = report.model_dump(mode="json")
    payload["review_status_counts"] = {"draft": 41, "reviewed": -5}

    with pytest.raises(ValueError, match="greater than or equal to 0"):
        type(report).model_validate(payload)

    for invalid_gap in (
        {"scenario_key": None, "dimension": "not-a-dimension", "missing_values": ["x"]},
        {
            "scenario_key": None,
            "dimension": CoverageDimension.CONTRAST_ROLE,
            "missing_values": ["x"],
            "unexpected": True,
        },
        {"scenario_key": None, "dimension": CoverageDimension.CONTRAST_ROLE, "missing_values": []},
        {
            "scenario_key": None,
            "dimension": CoverageDimension.CONTRAST_ROLE,
            "missing_values": ["   "],
        },
    ):
        with pytest.raises(ValueError):
            CoverageProgressGapV1.model_validate(invalid_gap)

    payload = report.model_dump(mode="json")
    payload["covered_dimension_counts"][CoverageDimension.INTENT.value] = -1

    with pytest.raises(ValueError, match="greater than or equal to 0"):
        type(report).model_validate(payload)
