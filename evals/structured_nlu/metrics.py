from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.schema import CasePrediction, EvaluationCase


@dataclass(frozen=True)
class ScoreCounts:
    cases: int
    first_attempt_contract_passes: int
    final_contract_passes: int
    retried_cases: int
    intent_matches: int
    action_matches: int
    slot_true_positives: int
    slot_false_positives: int
    slot_false_negatives: int
    gold_present_slots: int
    gold_absent_slots: int
    exact_value_matches: int
    hallucinated_slots: int
    omitted_slots: int
    applicable_change_fields: int
    change_field_matches: int


@dataclass(frozen=True)
class EvaluationScores:
    counts: ScoreCounts
    first_attempt_contract_success_rate: float
    final_contract_success_rate: float
    retry_rate: float
    complete_failure_rate: float
    intent_accuracy: float
    user_action_accuracy: float
    user_action_macro_f1: float
    slot_presence_precision: float
    slot_presence_recall: float
    slot_presence_f1: float
    slot_exact_match_rate: float
    hallucination_rate: float
    omission_rate: float
    change_field_accuracy: float | None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        return result


def score_predictions(
    cases: tuple[EvaluationCase, ...],
    predictions: tuple[CasePrediction, ...],
) -> EvaluationScores:
    if not cases:
        raise ValueError("at least one evaluation case is required")
    case_by_id = {case.id: case for case in cases}
    prediction_by_id = {prediction.case_id: prediction for prediction in predictions}
    if len(case_by_id) != len(cases):
        raise ValueError("evaluation case ids must be unique")
    if len(prediction_by_id) != len(predictions):
        raise ValueError("prediction case ids must be unique")
    if set(case_by_id) != set(prediction_by_id):
        missing = sorted(set(case_by_id) - set(prediction_by_id))
        extra = sorted(set(prediction_by_id) - set(case_by_id))
        raise ValueError(f"prediction ids do not match cases: missing={missing}, extra={extra}")

    first_passes = 0
    final_passes = 0
    retried = 0
    intent_matches = 0
    action_matches = 0
    action_gold: Counter[str] = Counter()
    action_predicted: Counter[str] = Counter()
    action_true_positive: Counter[str] = Counter()
    slot_tp = 0
    slot_fp = 0
    slot_fn = 0
    gold_present = 0
    gold_absent = 0
    exact_matches = 0
    hallucinated = 0
    omitted = 0
    applicable_change_fields = 0
    change_field_matches = 0

    for case_id, case in case_by_id.items():
        prediction = prediction_by_id[case_id]
        if prediction.attempts[0].contract_valid:
            first_passes += 1
        if len(prediction.attempts) == 2:
            retried += 1
        output = prediction.final_output
        if output is not None:
            contract = EVALUATION_CONTRACTS[case.scenario_key]
            if set(output.fields) != set(contract.field_names):
                raise ValueError(
                    f"prediction fields do not match {case.scenario_key}: {sorted(output.fields)}"
                )
            if output.intent not in contract.allowed_intents:
                raise ValueError(
                    f"prediction intent is not allowed for {case.scenario_key}: {output.intent}"
                )
            if output.user_action not in contract.user_actions:
                raise ValueError(
                    f"prediction user_action is not allowed for {case.scenario_key}: "
                    f"{output.user_action}"
                )
            final_passes += 1
            if output.intent == case.labels.intent:
                intent_matches += 1

        gold_action = case.labels.user_action
        predicted_action = output.user_action if output is not None else "__contract_failure__"
        action_gold[gold_action] += 1
        action_predicted[predicted_action] += 1
        if predicted_action == gold_action:
            action_matches += 1
            action_true_positive[gold_action] += 1

        for field_name, expected in case.labels.fields.items():
            predicted_value = output.fields.get(field_name) if output is not None else None
            expected_present = expected is not None
            predicted_present = predicted_value is not None
            if expected_present:
                gold_present += 1
                if predicted_present:
                    slot_tp += 1
                    if predicted_value in expected.accepted_values:
                        exact_matches += 1
                else:
                    slot_fn += 1
                    omitted += 1
            else:
                gold_absent += 1
                if predicted_present:
                    slot_fp += 1
                    hallucinated += 1

        if gold_action == "change_detail":
            applicable_change_fields += 1
            if output is not None and output.change_field == case.labels.change_field:
                change_field_matches += 1

    precision = _safe_ratio(slot_tp, slot_tp + slot_fp)
    recall = _safe_ratio(slot_tp, slot_tp + slot_fn)
    return EvaluationScores(
        counts=ScoreCounts(
            cases=len(cases),
            first_attempt_contract_passes=first_passes,
            final_contract_passes=final_passes,
            retried_cases=retried,
            intent_matches=intent_matches,
            action_matches=action_matches,
            slot_true_positives=slot_tp,
            slot_false_positives=slot_fp,
            slot_false_negatives=slot_fn,
            gold_present_slots=gold_present,
            gold_absent_slots=gold_absent,
            exact_value_matches=exact_matches,
            hallucinated_slots=hallucinated,
            omitted_slots=omitted,
            applicable_change_fields=applicable_change_fields,
            change_field_matches=change_field_matches,
        ),
        first_attempt_contract_success_rate=_safe_ratio(first_passes, len(cases)),
        final_contract_success_rate=_safe_ratio(final_passes, len(cases)),
        retry_rate=_safe_ratio(retried, len(cases)),
        complete_failure_rate=_safe_ratio(len(cases) - final_passes, len(cases)),
        intent_accuracy=_safe_ratio(intent_matches, len(cases)),
        user_action_accuracy=_safe_ratio(action_matches, len(cases)),
        user_action_macro_f1=_macro_f1(
            action_gold,
            action_predicted,
            action_true_positive,
        ),
        slot_presence_precision=precision,
        slot_presence_recall=recall,
        slot_presence_f1=_f1(precision, recall),
        slot_exact_match_rate=_safe_ratio(exact_matches, gold_present),
        hallucination_rate=_safe_ratio(hallucinated, gold_absent),
        omission_rate=_safe_ratio(omitted, gold_present),
        change_field_accuracy=(
            _safe_ratio(change_field_matches, applicable_change_fields)
            if applicable_change_fields
            else None
        ),
    )


def _macro_f1(
    gold: Counter[str],
    predicted: Counter[str],
    true_positive: Counter[str],
) -> float:
    class_scores = []
    for label in gold:
        tp = true_positive[label]
        precision = _safe_ratio(tp, predicted[label])
        recall = _safe_ratio(tp, gold[label])
        class_scores.append(_f1(precision, recall))
    return sum(class_scores) / len(class_scores)


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _safe_ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0
