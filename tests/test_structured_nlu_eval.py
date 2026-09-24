import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.metrics import score_predictions
from evals.structured_nlu.schema import (
    CasePrediction,
    EvaluationAttempt,
    EvaluationCase,
    ExpectedField,
    GoldLabels,
    NormalizedPrediction,
)


def _case(
    *,
    case_id: str,
    message: str,
    fields: dict[str, ExpectedField | None],
    action: str,
) -> EvaluationCase:
    return EvaluationCase(
        id=case_id,
        split="development",
        scenario_key="교수님:면담 예약",
        conversation_state="collecting_appointment_info",
        current_fields={},
        user_message=message,
        labels=GoldLabels(
            intent="appointment_booking",
            fields=fields,
            user_action=action,
            change_field=None,
        ),
        tags=("multi_field",),
        provenance="human_authored",
        review_status="adjudicated",
    )


def _appointment_fields(
    *,
    purpose: ExpectedField | None = None,
    date: ExpectedField | None = None,
    time: ExpectedField | None = None,
    name: ExpectedField | None = None,
) -> dict[str, ExpectedField | None]:
    return {
        "appointment_purpose": purpose,
        "date": date,
        "time": time,
        "user_name": name,
    }


def _prediction(
    case_id: str,
    *,
    fields: dict[str, str | None],
    action: str,
    retry: bool = False,
) -> CasePrediction:
    valid = EvaluationAttempt(
        contract_valid=True,
        latency_ms=100,
        output=NormalizedPrediction(
            intent="appointment_booking",
            fields=fields,
            user_action=action,
            change_field=None,
        ),
    )
    attempts = (
        (
            EvaluationAttempt(
                contract_valid=False,
                latency_ms=80,
                error_type="JSONDecodeError",
            ),
            valid,
        )
        if retry
        else (valid,)
    )
    return CasePrediction(case_id=case_id, attempts=attempts)


def test_json_schema_lists_the_same_scenarios_as_live_contracts():
    path = Path("evals/structured_nlu/gold_dataset.schema.json")
    schema = json.loads(path.read_text(encoding="utf-8"))
    scenario_values = schema["$defs"]["case"]["properties"]["scenario_key"]["enum"]

    assert set(scenario_values) == set(EVALUATION_CONTRACTS)
    assert len(scenario_values) == 16


def test_case_rejects_fields_that_do_not_match_the_live_extractor_contract():
    with pytest.raises(ValidationError, match="label fields must be exactly"):
        _case(
            case_id="appointment.invalid-fields",
            message="내일 면담 가능할까요?",
            fields={"date": ExpectedField(accepted_values=("내일",))},
            action="provide_appointment_info",
        )


def test_case_rejects_unreviewed_action_outside_the_live_contract():
    with pytest.raises(ValidationError, match="user_action is not allowed"):
        _case(
            case_id="appointment.invalid-action",
            message="내일 면담 가능할까요?",
            fields=_appointment_fields(
                date=ExpectedField(accepted_values=("내일",)),
            ),
            action="invented_action",
        )


def test_metrics_count_contract_retry_hallucination_omission_and_exact_values():
    cases = (
        _case(
            case_id="appointment.case-one",
            message="진로 상담 때문에 내일 뵙고 싶습니다.",
            fields=_appointment_fields(
                purpose=ExpectedField(accepted_values=("진로 상담",)),
                date=ExpectedField(accepted_values=("내일",)),
            ),
            action="provide_appointment_info",
        ),
        _case(
            case_id="appointment.case-two",
            message="과제 때문에 모레 오후 3시에 뵙고 싶습니다.",
            fields=_appointment_fields(
                purpose=ExpectedField(accepted_values=("과제", "과제 상담")),
                date=ExpectedField(accepted_values=("모레",)),
                time=ExpectedField(accepted_values=("오후 3시",)),
            ),
            action="provide_appointment_info",
        ),
    )
    predictions = (
        _prediction(
            "appointment.case-one",
            fields={
                "appointment_purpose": "진로 상담",
                "date": "내일",
                "time": "오후 2시",
                "user_name": None,
            },
            action="provide_appointment_info",
        ),
        _prediction(
            "appointment.case-two",
            fields={
                "appointment_purpose": "과제 상담",
                "date": None,
                "time": "오후 3시",
                "user_name": None,
            },
            action="unknown",
            retry=True,
        ),
    )

    scores = score_predictions(cases, predictions)

    assert scores.first_attempt_contract_success_rate == 0.5
    assert scores.final_contract_success_rate == 1.0
    assert scores.retry_rate == 0.5
    assert scores.complete_failure_rate == 0.0
    assert scores.intent_accuracy == 1.0
    assert scores.user_action_accuracy == 0.5
    assert scores.user_action_macro_f1 == pytest.approx(2 / 3)
    assert scores.slot_presence_precision == pytest.approx(4 / 5)
    assert scores.slot_presence_recall == pytest.approx(4 / 5)
    assert scores.slot_presence_f1 == pytest.approx(4 / 5)
    assert scores.slot_exact_match_rate == pytest.approx(4 / 5)
    assert scores.hallucination_rate == pytest.approx(1 / 3)
    assert scores.omission_rate == pytest.approx(1 / 5)
    assert scores.change_field_accuracy is None


def test_metrics_require_exactly_one_prediction_per_case():
    case = _case(
        case_id="appointment.missing-prediction",
        message="내일 면담 가능할까요?",
        fields=_appointment_fields(
            date=ExpectedField(accepted_values=("내일",)),
        ),
        action="provide_appointment_info",
    )

    with pytest.raises(ValueError, match="prediction ids do not match cases"):
        score_predictions((case,), ())


def test_metrics_reject_prediction_fields_outside_the_live_contract():
    case = _case(
        case_id="appointment.invalid-prediction-fields",
        message="내일 면담 가능할까요?",
        fields=_appointment_fields(
            date=ExpectedField(accepted_values=("내일",)),
        ),
        action="provide_appointment_info",
    )
    prediction = _prediction(
        case.id,
        fields={"date": "내일"},
        action="provide_appointment_info",
    )

    with pytest.raises(ValueError, match="prediction fields do not match"):
        score_predictions((case,), (prediction,))
