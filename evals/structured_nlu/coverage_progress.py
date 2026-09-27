from __future__ import annotations

import json
from collections import Counter
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.structured_nlu.benchmark import (
    OFFICIAL_BENCHMARK_PROFILE,
    OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT,
    CoverageCaseLike,
    CoverageDimension,
    corpus_fingerprint,
    inspect_benchmark_coverage,
)
from evals.structured_nlu.obligations import (
    AuthoringObligation,
    build_official_authoring_obligations,
)
from evals.structured_nlu.schema import DatasetSplit, GoldDataset, ReviewStatus

COVERAGE_PROGRESS_SCHEMA_VERSION = 1
COVERAGE_PROGRESS_REPORT_ID = "maeumcall-structured-nlu-development-progress-v1"
COVERAGE_PROGRESS_QUALIFICATION = "unqualified_development_diagnostic"
_UNVERIFIED_SEMANTIC_TAGS = frozenset({"ambiguous", "colloquial", "ellipsis", "negation"})
CoverageProgressValue = Annotated[str, Field(min_length=1, pattern=r".*\S.*")]
_SUPPORTED_PROGRESS_DIMENSIONS = frozenset(
    {
        CoverageDimension.ACTION_FIELD_ABSENT,
        CoverageDimension.ACTION_FIELD_PRESENT,
        CoverageDimension.ALTERNATIVE_TIME_RELATION,
        CoverageDimension.CHANGE_FIELD,
        CoverageDimension.CONTRAST_ROLE,
        CoverageDimension.CURRENT_DELTA_RELATION,
        CoverageDimension.CURRENT_FIELD_ABSENT,
        CoverageDimension.CURRENT_FIELD_OPTION,
        CoverageDimension.CURRENT_FIELD_PRESENT,
        CoverageDimension.CURRENT_FIELDS_CONTEXT,
        CoverageDimension.FIELD_ABSENT,
        CoverageDimension.FIELD_OPTION,
        CoverageDimension.FIELD_PRESENT,
        CoverageDimension.INTENT,
        CoverageDimension.SCENARIO_DIFFICULTY_TAG,
        CoverageDimension.STATE_ACTION,
    }
)


class CoverageProgressGapV1(BaseModel):
    """Group exact missing values by scenario and coverage dimension."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_key: str | None
    dimension: CoverageDimension
    missing_values: tuple[CoverageProgressValue, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def values_are_unique_and_sorted(self) -> CoverageProgressGapV1:
        if tuple(sorted(set(self.missing_values))) != self.missing_values:
            raise ValueError("coverage progress gap values must be unique and sorted")
        return self


class CoverageProgressReportV1(BaseModel):
    """Describe draft coverage without presenting it as an official benchmark result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    coverage_progress_schema_version: Literal[COVERAGE_PROGRESS_SCHEMA_VERSION]
    report_id: Literal[COVERAGE_PROGRESS_REPORT_ID]
    qualification_status: Literal[COVERAGE_PROGRESS_QUALIFICATION]
    profile_id: Literal["maeumcall-structured-nlu-v3"]
    profile_fingerprint: Literal[OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT]
    corpus_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    split: Literal[DatasetSplit.DEVELOPMENT]
    case_count: int = Field(ge=0)
    review_status_counts: dict[ReviewStatus, Annotated[int, Field(ge=0)]]
    required_obligation_count: int = Field(gt=0)
    covered_obligation_count: int = Field(ge=0)
    missing_obligation_count: int = Field(ge=0)
    covered_dimension_counts: dict[CoverageDimension, Annotated[int, Field(ge=0)]]
    missing_dimension_counts: dict[CoverageDimension, Annotated[int, Field(ge=0)]]
    missing_obligations: tuple[CoverageProgressGapV1, ...]

    @model_validator(mode="after")
    def counts_match_the_exact_inventory(self) -> CoverageProgressReportV1:
        if self.profile_id != OFFICIAL_BENCHMARK_PROFILE.profile_id:
            raise ValueError("coverage progress profile id must match the official profile")
        if self.profile_fingerprint != OFFICIAL_BENCHMARK_PROFILE.fingerprint:
            raise ValueError(
                "coverage progress profile fingerprint must match the official profile"
            )
        if sum(self.review_status_counts.values()) != self.case_count:
            raise ValueError("review status counts must equal the development case count")
        if self.covered_obligation_count + self.missing_obligation_count != (
            self.required_obligation_count
        ):
            raise ValueError("coverage progress counts must equal the required inventory")
        if sum(self.covered_dimension_counts.values()) != self.covered_obligation_count:
            raise ValueError("covered dimension counts must equal the covered obligation count")
        if sum(self.missing_dimension_counts.values()) != self.missing_obligation_count:
            raise ValueError("missing dimension counts must equal the missing obligation count")
        if sum(len(gap.missing_values) for gap in self.missing_obligations) != (
            self.missing_obligation_count
        ):
            raise ValueError("missing obligation groups must equal the missing obligation count")
        gap_keys = [(gap.scenario_key, gap.dimension.value) for gap in self.missing_obligations]
        expected_gap_keys = sorted(
            set(gap_keys),
            key=lambda key: ("" if key[0] is None else key[0], key[1]),
        )
        if gap_keys != expected_gap_keys:
            raise ValueError("coverage progress gaps must have unique sorted scopes")
        grouped_missing_counts: Counter[CoverageDimension] = Counter()
        for gap in self.missing_obligations:
            grouped_missing_counts[gap.dimension] += len(gap.missing_values)
        if dict(grouped_missing_counts) != self.missing_dimension_counts:
            raise ValueError("missing groups must match the missing dimension counts")
        official_obligations = build_official_authoring_obligations()
        required_counts = Counter(item.dimension for item in official_obligations)
        combined_counts = Counter(self.covered_dimension_counts)
        combined_counts.update(self.missing_dimension_counts)
        if combined_counts != required_counts:
            raise ValueError("coverage dimensions must match the official obligation inventory")
        official_keys = {_obligation_key(item) for item in official_obligations}
        reported_missing_keys = {
            (gap.scenario_key, gap.dimension, value)
            for gap in self.missing_obligations
            for value in gap.missing_values
        }
        if not reported_missing_keys <= official_keys:
            raise ValueError("coverage progress gaps must reference official obligations")
        return self


def build_development_coverage_progress(
    dataset: GoldDataset,
    *,
    diagnostic_cases: tuple[CoverageCaseLike, ...] = (),
) -> CoverageProgressReportV1:
    """Compare development drafts with the V3 inventory without qualifying the split."""
    official = build_official_authoring_obligations()
    official_dimensions = frozenset(item.dimension for item in official)
    if official_dimensions != _SUPPORTED_PROGRESS_DIMENSIONS:
        raise RuntimeError(
            "coverage progress dimension support must exactly match the official inventory"
        )
    official_by_key = {_obligation_key(obligation): obligation for obligation in official}
    diagnostic = inspect_benchmark_coverage(
        dataset,
        split=DatasetSplit.DEVELOPMENT,
        profile=OFFICIAL_BENCHMARK_PROFILE,
        diagnostic_cases=diagnostic_cases,
    )
    missing_keys = {
        (issue.scenario_key, issue.dimension, value)
        for issue in diagnostic.issues
        for value in issue.missing_values
        if (issue.scenario_key, issue.dimension, value) in official_by_key
    }
    present_scenarios = {
        case.scenario_key for case in dataset.cases if case.split is DatasetSplit.DEVELOPMENT
    }
    adjudicated_semantic_tags = {
        (case.scenario_key, tag.value)
        for case in dataset.cases
        if case.split is DatasetSplit.DEVELOPMENT and case.review_status is ReviewStatus.ADJUDICATED
        for tag in case.tags
        if tag.value in _UNVERIFIED_SEMANTIC_TAGS
    }
    missing_keys.update(
        key for key in official_by_key if key[0] is not None and key[0] not in present_scenarios
    )
    missing_keys.update(
        key
        for key in official_by_key
        if key[1] is CoverageDimension.SCENARIO_DIFFICULTY_TAG
        and key[2] in _UNVERIFIED_SEMANTIC_TAGS
        and (key[0], key[2]) not in adjudicated_semantic_tags
    )
    missing_keys.update(key for key in official_by_key if key[1] is CoverageDimension.CONTRAST_ROLE)
    missing = tuple(official_by_key[key] for key in sorted(missing_keys, key=_sort_key))
    covered = tuple(
        obligation for obligation in official if _obligation_key(obligation) not in missing_keys
    )
    development_cases = tuple(
        case for case in dataset.cases if case.split is DatasetSplit.DEVELOPMENT
    )
    return CoverageProgressReportV1(
        coverage_progress_schema_version=COVERAGE_PROGRESS_SCHEMA_VERSION,
        report_id=COVERAGE_PROGRESS_REPORT_ID,
        qualification_status=COVERAGE_PROGRESS_QUALIFICATION,
        profile_id=OFFICIAL_BENCHMARK_PROFILE.profile_id,
        profile_fingerprint=OFFICIAL_BENCHMARK_PROFILE.fingerprint,
        corpus_fingerprint=corpus_fingerprint(dataset),
        split=DatasetSplit.DEVELOPMENT,
        case_count=len(development_cases),
        review_status_counts=dict(
            sorted(Counter(case.review_status for case in development_cases).items())
        ),
        required_obligation_count=len(official),
        covered_obligation_count=len(covered),
        missing_obligation_count=len(missing),
        covered_dimension_counts=_dimension_counts(covered),
        missing_dimension_counts=_dimension_counts(missing),
        missing_obligations=_group_missing_obligations(missing),
    )


def serialize_development_coverage_progress(dataset: GoldDataset) -> str:
    report = build_development_coverage_progress(dataset)
    payload = report.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _dimension_counts(
    obligations: tuple[AuthoringObligation, ...],
) -> dict[CoverageDimension, int]:
    return dict(sorted(Counter(item.dimension for item in obligations).items()))


def _group_missing_obligations(
    obligations: tuple[AuthoringObligation, ...],
) -> tuple[CoverageProgressGapV1, ...]:
    values_by_scope: dict[tuple[str | None, CoverageDimension], list[str]] = {}
    for obligation in obligations:
        key = obligation.scenario_key, obligation.dimension
        values_by_scope.setdefault(key, []).append(obligation.value)
    return tuple(
        CoverageProgressGapV1(
            scenario_key=scenario_key,
            dimension=dimension,
            missing_values=tuple(sorted(values)),
        )
        for (scenario_key, dimension), values in sorted(
            values_by_scope.items(),
            key=lambda item: (
                "" if item[0][0] is None else item[0][0],
                item[0][1].value,
            ),
        )
    )


def _obligation_key(
    obligation: AuthoringObligation,
) -> tuple[str | None, CoverageDimension, str]:
    return obligation.scenario_key, obligation.dimension, obligation.value


def _sort_key(
    key: tuple[str | None, CoverageDimension, str],
) -> tuple[str, str, str]:
    scenario_key, dimension, value = key
    return "" if scenario_key is None else scenario_key, dimension.value, value
