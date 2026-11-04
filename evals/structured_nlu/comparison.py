"""Compare full-case accuracy on one adjudicated test slice.

This helper does not replace the official freeze-record and coverage gates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from evals.structured_nlu.metrics import score_predictions
from evals.structured_nlu.schema import CasePrediction, DatasetSplit, EvaluationCase


@dataclass(frozen=True)
class PairedAccuracyComparison:
    cases: int
    baseline_correct: int
    candidate_correct: int
    baseline_accuracy: float
    candidate_accuracy: float
    difference_percentage_points: float
    relative_change_percent: float | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SlicedPairedAccuracyComparison:
    """Paired exact-match comparisons for overlapping test-case slices."""

    overall: PairedAccuracyComparison
    by_scenario: dict[str, PairedAccuracyComparison]
    by_tag: dict[str, PairedAccuracyComparison]

    def to_dict(self) -> dict:
        return asdict(self)


def compare_test_predictions(
    cases: tuple[EvaluationCase, ...],
    baseline: tuple[CasePrediction, ...],
    candidate: tuple[CasePrediction, ...],
) -> PairedAccuracyComparison:
    """Score both candidates against exactly the same adjudicated test cases."""
    if not cases or any(case.split is not DatasetSplit.TEST for case in cases):
        raise ValueError("paired comparison requires nonempty test cases only")

    baseline_scores = score_predictions(cases, baseline)
    candidate_scores = score_predictions(cases, candidate)
    baseline_rate = baseline_scores.case_exact_match_rate
    candidate_rate = candidate_scores.case_exact_match_rate
    return PairedAccuracyComparison(
        cases=len(cases),
        baseline_correct=baseline_scores.counts.fully_correct_cases,
        candidate_correct=candidate_scores.counts.fully_correct_cases,
        baseline_accuracy=baseline_rate,
        candidate_accuracy=candidate_rate,
        difference_percentage_points=(candidate_rate - baseline_rate) * 100,
        relative_change_percent=(
            (candidate_rate - baseline_rate) / baseline_rate * 100 if baseline_rate > 0 else None
        ),
    )


def compare_test_predictions_by_slice(
    cases: tuple[EvaluationCase, ...],
    baseline: tuple[CasePrediction, ...],
    candidate: tuple[CasePrediction, ...],
) -> SlicedPairedAccuracyComparison:
    """Compare the same test cases in each scenario and tag slice.

    This low-level helper still requires the official freeze-record gate before
    its output can be published as an official benchmark result.
    """
    overall = compare_test_predictions(cases, baseline, candidate)
    baseline_by_id = {prediction.case_id: prediction for prediction in baseline}
    candidate_by_id = {prediction.case_id: prediction for prediction in candidate}

    def compare_group(group: tuple[EvaluationCase, ...]) -> PairedAccuracyComparison:
        return compare_test_predictions(
            group,
            tuple(baseline_by_id[case.id] for case in group),
            tuple(candidate_by_id[case.id] for case in group),
        )

    return SlicedPairedAccuracyComparison(
        overall=overall,
        by_scenario={
            scenario: compare_group(tuple(case for case in cases if case.scenario_key == scenario))
            for scenario in sorted({case.scenario_key for case in cases})
        },
        by_tag={
            tag: compare_group(tuple(case for case in cases if tag in case.tags))
            for tag in sorted({str(tag) for case in cases for tag in case.tags})
        },
    )
