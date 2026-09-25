import copy
import json
import unicodedata
from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.structured_nlu.benchmark import (
    OFFICIAL_BENCHMARK_PROFILE,
    OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT,
    BenchmarkCoverageReport,
    BenchmarkProfile,
    CoverageDimension,
    CoverageIssue,
    QualifiedTestSlice,
    ScenarioCoverageRequirement,
    _append_v3_scenario_coverage_issues,
    _prepare_qualified_test_slice,
    _score_qualified_test_slice,
    inspect_benchmark_coverage,
    prepare_benchmark_slice,
)
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.contrast import (
    DETAILED_POSITIVE_CONTRASTS_V1,
    OFFICIAL_CONTRAST_FAMILIES_V1,
    ContrastFamilyPolicy,
    ContrastGroupDefinition,
    ContrastRolePolicy,
    contrast_group_fingerprint,
    verify_contrast_manifest,
)
from evals.structured_nlu.coverage_v3 import OFFICIAL_COVERAGE_CONTRACT_V3
from evals.structured_nlu.metrics import score_predictions
from evals.structured_nlu.review import evaluation_case_fingerprint
from evals.structured_nlu.schema import (
    CasePrediction,
    DatasetSplit,
    DifficultyTag,
    EvaluationAttempt,
    EvaluationCase,
    ExpectedField,
    GoldDataset,
    GoldLabels,
    NormalizedPrediction,
)
from evals.structured_nlu.semantics import ACTION_OBJECTIVE_TAGS_V1
from services.flow.common.state_contract import SCENARIO_STATE_VERSION
from services.flow.delivery.contracts import ORDER_CHANGE_SPEC


def _case(
    *,
    case_id: str,
    message: str,
    fields: dict[str, ExpectedField | None],
    action: str,
    tags: tuple[str, ...],
    conversation_group_id: str | None = None,
    review_status: str = "adjudicated",
    conversation_state: str = "collecting_appointment_info",
    split: str = "development",
) -> EvaluationCase:
    return EvaluationCase(
        id=case_id,
        conversation_group_id=conversation_group_id or case_id,
        split=split,
        scenario_key="교수님:면담 예약",
        conversation_state=conversation_state,
        current_fields={},
        offered_alternative_times=(),
        user_message=message,
        labels=GoldLabels(
            intent="appointment_booking",
            fields=fields,
            user_action=action,
            change_field=None,
        ),
        tags=tags,
        provenance="human_authored",
        review_status=review_status,
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


def _approved_contrast_group(definition: dict) -> dict:
    parsed = ContrastGroupDefinition.model_validate(definition)
    return {
        "definition": definition,
        "approval": {
            "group_fingerprint_algorithm": "contrast-group-canonical-json-sha256-v1",
            "group_fingerprint": contrast_group_fingerprint(parsed),
            "reviewer_id": "reviewer.primary",
            "reviewed_at": "2026-09-26T09:00:00+09:00",
            "rationale": "공유 문맥에서 두 행동 역할이 실제 혼동 축을 이룬다고 검수했다.",
            "decision": "approved",
        },
    }


def _refresh_contrast_group_approval(group: dict) -> None:
    definition = ContrastGroupDefinition.model_validate(group["definition"])
    group["approval"]["group_fingerprint"] = contrast_group_fingerprint(definition)


def _prediction(
    case_id: str,
    *,
    fields: dict[str, str | None],
    action: str,
    retry: bool = False,
    intent: str | None = "appointment_booking",
    change_field: str | None = None,
) -> CasePrediction:
    valid = EvaluationAttempt(
        contract_valid=True,
        latency_ms=100,
        output=NormalizedPrediction(
            intent=intent,
            fields=fields,
            user_action=action,
            change_field=change_field,
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


def _order_change_case(
    *,
    case_id: str,
    conversation_state: str,
    current_fields: dict[str, str | None],
    labels: dict[str, ExpectedField | None],
    action: str,
    tags: tuple[str, ...],
) -> EvaluationCase:
    return EvaluationCase(
        id=case_id,
        conversation_group_id=case_id,
        split="development",
        scenario_key="배달:주문 변경",
        conversation_state=conversation_state,
        current_fields=current_fields,
        offered_alternative_times=(),
        user_message="주문 변경을 도와주세요.",
        labels=GoldLabels(
            intent="delivery_order_change",
            fields=labels,
            user_action=action,
            change_field=None,
        ),
        tags=tags,
        provenance="human_authored",
        review_status="adjudicated",
    )


def test_json_schema_lists_the_same_scenarios_as_live_contracts():
    path = Path("evals/structured_nlu/gold_dataset.schema.json")
    schema = json.loads(path.read_text(encoding="utf-8"))
    scenario_values = schema["$defs"]["case"]["properties"]["scenario_key"]["enum"]

    assert set(scenario_values) == set(EVALUATION_CONTRACTS)
    assert len(scenario_values) == 16


def test_json_schema_rejects_whitespace_only_text_like_the_runtime_schema():
    path = Path("evals/structured_nlu/gold_dataset.schema.json")
    schema = json.loads(path.read_text(encoding="utf-8"))

    assert schema["$defs"]["nullableText"]["oneOf"][0]["pattern"] == r"\S"
    assert (
        schema["$defs"]["expectedField"]["oneOf"][0]["properties"]["accepted_values"]["items"][
            "pattern"
        ]
        == r"\S"
    )
    assert schema["$defs"]["case"]["properties"]["user_message"]["pattern"] == r"\S"
    assert schema["$defs"]["case"]["properties"]["conversation_state"]["pattern"] == r"\S"
    assert schema["$defs"]["labels"]["properties"]["user_action"]["pattern"] == r"\S"


def test_case_rejects_fields_that_do_not_match_the_live_extractor_contract():
    with pytest.raises(ValidationError, match="label fields must be exactly"):
        _case(
            case_id="appointment.invalid-fields",
            message="내일 면담 가능할까요?",
            fields={"date": ExpectedField(accepted_values=("내일",))},
            action="provide_appointment_info",
            tags=("single_field",),
        )


def test_case_rejects_whitespace_only_gold_value():
    with pytest.raises(ValidationError, match="at least 1 character"):
        _case(
            case_id="appointment.blank-gold-value",
            message="내일 면담 가능할까요?",
            fields=_appointment_fields(
                date=ExpectedField(accepted_values=("   ",)),
            ),
            action="provide_appointment_info",
            tags=("single_field",),
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
            tags=("single_field",),
        )


def test_case_rejects_globally_known_action_from_wrong_conversation_state():
    with pytest.raises(ValidationError, match="user_action is not allowed"):
        _case(
            case_id="appointment.wrong-state-action",
            message="통화를 마칠게요.",
            fields=_appointment_fields(),
            action="end_call",
            tags=("ambiguous",),
        )


def test_case_rejects_workflow_gold_value_outside_live_options():
    with pytest.raises(ValidationError, match="accepted_values are not allowed"):
        EvaluationCase(
            id="delivery.invalid-gold-option",
            conversation_group_id="delivery.invalid-gold-option",
            split="development",
            scenario_key="배달:주문 변경",
            conversation_state="collecting_order_change",
            current_fields={
                "order_number": None,
                "change_type": None,
                "requested_change": None,
                "unavailable_preference": None,
            },
            offered_alternative_times=(),
            user_message="배송지를 바꾸고 싶어요.",
            labels=GoldLabels(
                intent="delivery_order_change",
                fields={
                    "order_number": None,
                    "change_type": ExpectedField(accepted_values=("not-a-real-option",)),
                    "requested_change": None,
                    "unavailable_preference": None,
                },
                user_action="provide_details",
                change_field=None,
            ),
            tags=("single_field",),
            provenance="human_authored",
            review_status="adjudicated",
        )


def test_case_rejects_multiple_canonical_values_for_one_option_field():
    with pytest.raises(
        ValidationError,
        match="option fields require exactly one canonical accepted value",
    ):
        EvaluationCase(
            id="delivery.multiple-gold-options",
            conversation_group_id="delivery.multiple-gold-options",
            split="development",
            scenario_key="배달:주문 변경",
            conversation_state="collecting_order_change",
            current_fields={
                "order_number": None,
                "change_type": None,
                "requested_change": None,
                "unavailable_preference": None,
            },
            offered_alternative_times=(),
            user_message="배송지나 메뉴 수량을 바꾸고 싶어요.",
            labels=GoldLabels(
                intent="delivery_order_change",
                fields={
                    "order_number": None,
                    "change_type": ExpectedField(
                        accepted_values=("delivery_address", "menu_or_quantity")
                    ),
                    "requested_change": None,
                    "unavailable_preference": None,
                },
                user_action="provide_details",
                change_field=None,
            ),
            tags=("single_field", "ambiguous"),
            provenance="human_authored",
            review_status="adjudicated",
        )


def test_case_rejects_workflow_current_option_outside_live_contract():
    with pytest.raises(ValidationError, match="workflow field option is invalid"):
        _order_change_case(
            case_id="delivery.invalid-current-option",
            conversation_state="collecting_order_change",
            current_fields={
                "order_number": None,
                "change_type": "not-a-real-option",
                "requested_change": None,
                "unavailable_preference": None,
            },
            labels={
                "order_number": None,
                "change_type": None,
                "requested_change": ExpectedField(accepted_values=("새 주소",)),
                "unavailable_preference": None,
            },
            action="provide_details",
            tags=("single_field",),
        )


def test_case_rejects_incomplete_current_fields_in_confirming_workflow_state():
    with pytest.raises(ValidationError, match="current state requires complete fields"):
        _order_change_case(
            case_id="delivery.incomplete-confirmation",
            conversation_state="confirming_order_change",
            current_fields={
                "order_number": "ORDER-1234",
                "change_type": "delivery_address",
                "requested_change": None,
                "unavailable_preference": "keep_order",
            },
            labels={
                "order_number": None,
                "change_type": None,
                "requested_change": None,
                "unavailable_preference": None,
            },
            action="confirm_details",
            tags=("confirmation",),
        )


def test_case_rejects_field_count_tag_that_does_not_match_labels():
    with pytest.raises(ValidationError, match="multi_field tag requires"):
        _case(
            case_id="appointment.invalid-field-count-tag",
            message="내일 가능합니다.",
            fields=_appointment_fields(
                date=ExpectedField(accepted_values=("내일",)),
            ),
            action="provide_appointment_info",
            tags=("single_field", "multi_field"),
        )


def test_case_requires_objective_field_count_tag():
    with pytest.raises(ValidationError, match="single_field tag is required"):
        _case(
            case_id="appointment.missing-field-count-tag",
            message="내일 가능합니다.",
            fields=_appointment_fields(
                date=ExpectedField(accepted_values=("내일",)),
            ),
            action="provide_appointment_info",
            tags=("ambiguous",),
        )


def test_case_requires_objective_action_tag():
    with pytest.raises(ValidationError, match="objective tags must exactly match"):
        _case(
            case_id="appointment.missing-correction-tag",
            message="날짜를 내일로 바꿀게요.",
            fields=_appointment_fields(
                date=ExpectedField(accepted_values=("내일",)),
            ),
            action="change_date",
            conversation_state="confirming_info",
            tags=("single_field",),
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
            tags=("multi_field",),
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
            tags=("multi_field",),
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
            action="provide_appointment_info",
            retry=True,
        ),
    )

    scores = score_predictions(cases, predictions)

    assert scores.first_attempt_contract_success_rate == 0.5
    assert scores.final_contract_success_rate == 1.0
    assert scores.retry_rate == 0.5
    assert scores.complete_failure_rate == 0.0
    assert scores.intent_accuracy == 1.0
    assert scores.user_action_accuracy == 1.0
    assert scores.user_action_macro_f1 == 1.0
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
        tags=("single_field",),
    )

    with pytest.raises(ValueError, match="prediction ids do not match cases"):
        score_predictions((case,), ())


def test_metrics_reject_cases_that_have_not_completed_adjudication():
    case = _case(
        case_id="appointment.draft-case",
        message="내일 면담 가능할까요?",
        fields=_appointment_fields(date=ExpectedField(accepted_values=("내일",))),
        action="provide_appointment_info",
        tags=("single_field",),
        review_status="draft",
    )
    prediction = _prediction(
        case.id,
        fields={
            "appointment_purpose": None,
            "date": "내일",
            "time": None,
            "user_name": None,
        },
        action="provide_appointment_info",
    )

    with pytest.raises(ValueError, match="requires adjudicated cases only"):
        score_predictions((case,), (prediction,))


def test_metrics_count_prediction_fields_outside_the_live_contract_as_contract_failure():
    case = _case(
        case_id="appointment.invalid-prediction-fields",
        message="내일 면담 가능할까요?",
        fields=_appointment_fields(
            date=ExpectedField(accepted_values=("내일",)),
        ),
        action="provide_appointment_info",
        tags=("single_field",),
    )
    prediction = _prediction(
        case.id,
        fields={"date": "내일"},
        action="provide_appointment_info",
    )

    scores = score_predictions((case,), (prediction,))

    assert scores.final_contract_success_rate == 0.0
    assert scores.complete_failure_rate == 1.0
    assert scores.counts.gold_present_slots == 0
    assert scores.counts.gold_absent_slots == 0


def test_metrics_count_action_from_wrong_state_as_contract_failure():
    case = _case(
        case_id="appointment.invalid-state-action-prediction",
        message="네, 맞습니다.",
        fields=_appointment_fields(),
        action="confirm_info",
        tags=("confirmation",),
        conversation_state="confirming_info",
    )
    prediction = _prediction(
        case.id,
        fields={
            "appointment_purpose": None,
            "date": None,
            "time": None,
            "user_name": None,
        },
        action="end_call",
    )

    scores = score_predictions((case,), (prediction,))

    assert scores.final_contract_success_rate == 0.0
    assert scores.complete_failure_rate == 1.0
    assert scores.counts.gold_present_slots == 0
    assert scores.counts.gold_absent_slots == 0


def _appointment_test_profile() -> BenchmarkProfile:
    contract = EVALUATION_CONTRACTS["교수님:면담 예약"]
    return BenchmarkProfile(
        profile_id="appointment-contract-test-v1",
        scenarios=(
            (
                "교수님:면담 예약",
                ScenarioCoverageRequirement(
                    conversation_states=frozenset({"collecting_appointment_info"}),
                    user_actions=frozenset({"provide_appointment_info", "unknown"}),
                    fields=frozenset(_appointment_fields()),
                    change_fields=frozenset(),
                    allowed_intents=contract.allowed_intents,
                    actions_by_state=(
                        (
                            "collecting_appointment_info",
                            frozenset({"provide_appointment_info", "unknown"}),
                        ),
                    ),
                    field_options=contract.field_options,
                    scoring_contract_payload=contract.scoring_contract_payload,
                    action_field_present=frozenset(
                        item
                        for item in contract.action_field_coverage[0]
                        if item.split("->", 1)[0] in {"provide_appointment_info", "unknown"}
                    ),
                    action_field_absent=frozenset(),
                ),
            ),
        ),
        required_tags=frozenset({DifficultyTag.SINGLE_FIELD, DifficultyTag.MULTI_FIELD}),
    )


def _gold_dataset(*cases: EvaluationCase) -> GoldDataset:
    return GoldDataset(
        dataset_version=2,
        state_contract_version=SCENARIO_STATE_VERSION,
        cases=cases,
    )


def test_gold_dataset_rejects_one_conversation_group_across_splits():
    development_case = _case(
        case_id="appointment.group-development",
        conversation_group_id="appointment.shared-conversation",
        message="내일 면담하고 싶습니다.",
        fields=_appointment_fields(
            date=ExpectedField(accepted_values=("내일",)),
        ),
        action="provide_appointment_info",
        tags=("single_field",),
    )
    test_case = _case(
        case_id="appointment.group-test",
        conversation_group_id="appointment.shared-conversation",
        message="모레 면담을 부탁드립니다.",
        fields=_appointment_fields(
            date=ExpectedField(accepted_values=("모레",)),
        ),
        action="provide_appointment_info",
        split="test",
        tags=("single_field",),
    )

    with pytest.raises(ValidationError, match="conversation groups must not cross splits"):
        _gold_dataset(development_case, test_case)


def test_gold_dataset_rejects_identical_inputs_across_splits_even_with_different_groups():
    development_case = _case(
        case_id="appointment.duplicate-development",
        conversation_group_id="appointment.development-family",
        message="내일 면담하고 싶습니다.",
        fields=_appointment_fields(
            date=ExpectedField(accepted_values=("내일",)),
        ),
        action="provide_appointment_info",
        tags=("single_field",),
    )
    test_case = _case(
        case_id="appointment.duplicate-test",
        conversation_group_id="appointment.test-family",
        message="내일 면담하고 싶습니다.",
        fields=_appointment_fields(
            date=ExpectedField(accepted_values=("내일",)),
        ),
        action="provide_appointment_info",
        split="test",
        tags=("single_field",),
    )

    with pytest.raises(ValidationError, match="duplicate evaluation inputs are not allowed"):
        _gold_dataset(development_case, test_case)


def test_gold_dataset_allows_same_message_in_different_model_contexts():
    development_case = _case(
        case_id="appointment.same-message-collecting",
        conversation_group_id="appointment.collecting-family",
        message="네, 그렇게 해 주세요.",
        fields=_appointment_fields(),
        action="unknown",
        tags=("ambiguous", "hard_negative"),
    )
    test_case = _case(
        case_id="appointment.same-message-confirming",
        conversation_group_id="appointment.confirming-family",
        message="네, 그렇게 해 주세요.",
        fields=_appointment_fields(),
        action="confirm_info",
        conversation_state="confirming_info",
        split="test",
        tags=("confirmation",),
    )

    dataset = _gold_dataset(development_case, test_case)

    assert len(dataset.cases) == 2


def test_gold_dataset_rejects_unicode_equivalent_inputs_across_splits():
    development_case = _case(
        case_id="appointment.unicode-development",
        conversation_group_id="appointment.unicode-development",
        message="김하늘 학생입니다.",
        fields=_appointment_fields(
            name=ExpectedField(accepted_values=("김하늘",)),
        ),
        action="provide_appointment_info",
        tags=("single_field",),
    )
    test_case = _case(
        case_id="appointment.unicode-test",
        conversation_group_id="appointment.unicode-test",
        message="김하늘 학생입니다.",
        fields=_appointment_fields(
            name=ExpectedField(accepted_values=("김하늘",)),
        ),
        action="provide_appointment_info",
        split="test",
        tags=("single_field",),
    )

    with pytest.raises(ValidationError, match="duplicate evaluation inputs are not allowed"):
        _gold_dataset(development_case, test_case)


def test_gold_dataset_rejects_duplicate_inputs_inside_one_split():
    first_case = _case(
        case_id="appointment.duplicate-first",
        conversation_group_id="appointment.duplicate-first",
        message="내일 면담하고 싶습니다.",
        fields=_appointment_fields(date=ExpectedField(accepted_values=("내일",))),
        action="provide_appointment_info",
        tags=("single_field",),
    )
    second_case = first_case.model_copy(
        update={
            "id": "appointment.duplicate-second",
            "conversation_group_id": "appointment.duplicate-second",
        }
    )

    with pytest.raises(ValidationError, match="duplicate evaluation inputs are not allowed"):
        _gold_dataset(first_case, second_case)


def test_gold_dataset_rejects_conflicting_labels_for_one_input():
    first_case = _case(
        case_id="appointment.conflict-first",
        conversation_group_id="appointment.conflict-first",
        message="그날 면담하고 싶습니다.",
        fields=_appointment_fields(date=ExpectedField(accepted_values=("내일",))),
        action="provide_appointment_info",
        tags=("single_field", "ambiguous"),
    )
    second_case = _case(
        case_id="appointment.conflict-second",
        conversation_group_id="appointment.conflict-second",
        message="그날 면담하고 싶습니다.",
        fields=_appointment_fields(date=ExpectedField(accepted_values=("모레",))),
        action="provide_appointment_info",
        tags=("single_field", "ambiguous"),
    )

    with pytest.raises(ValidationError, match="identical evaluation inputs have conflicting"):
        _gold_dataset(first_case, second_case)


def test_case_rejects_alternative_times_unused_by_the_model_input():
    with pytest.raises(ValidationError, match="allowed only in an alternative-selection state"):
        EvaluationCase(
            id="appointment.irrelevant-alternatives",
            conversation_group_id="appointment.irrelevant-alternatives",
            split="development",
            scenario_key="교수님:면담 예약",
            conversation_state="collecting_appointment_info",
            current_fields={},
            offered_alternative_times=("오후 4시",),
            user_message="내일 면담하고 싶습니다.",
            labels=GoldLabels(
                intent="appointment_booking",
                fields=_appointment_fields(
                    date=ExpectedField(accepted_values=("내일",)),
                ),
                user_action="provide_appointment_info",
                change_field=None,
            ),
            tags=("single_field",),
            provenance="human_authored",
            review_status="adjudicated",
        )


def test_official_profile_tracks_all_live_structured_nlu_contracts():
    requirements = OFFICIAL_BENCHMARK_PROFILE.scenario_requirements

    assert set(requirements) == set(EVALUATION_CONTRACTS)
    assert len(requirements) == 16
    assert OFFICIAL_BENCHMARK_PROFILE.fingerprint == OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT
    for scenario_key, contract in EVALUATION_CONTRACTS.items():
        requirement = requirements[scenario_key]
        assert requirement.conversation_states == contract.conversation_states
        assert requirement.user_actions == contract.user_actions
        assert requirement.fields == frozenset(contract.field_names)
        assert dict(requirement.actions_by_state) == dict(contract.actions_by_state)
        assert requirement.allowed_intents == contract.allowed_intents
        assert requirement.field_options == contract.field_options
        assert requirement.scoring_contract_payload == contract.scoring_contract_payload
        assert (
            requirement.action_field_present,
            requirement.action_field_absent,
        ) == contract.action_field_coverage


def test_v3_difficulty_tags_are_required_per_scenario():
    case = _case(
        case_id="appointment.v3-tag-scope",
        message="내일 면담하고 싶습니다.",
        fields=_appointment_fields(date=ExpectedField(accepted_values=("내일",))),
        action="provide_appointment_info",
        tags=("single_field",),
    )
    issues = []

    _append_v3_scenario_coverage_issues(
        issues,
        scenario_key="교수님:면담 예약",
        scenario_cases=(case,),
    )

    tag_issue = next(
        issue for issue in issues if issue.dimension is CoverageDimension.SCENARIO_DIFFICULTY_TAG
    )
    assert tag_issue.scenario_key == "교수님:면담 예약"
    assert "hard_negative" in tag_issue.missing_values
    assert "confirmation" in tag_issue.missing_values


def test_v3_profile_has_context_and_contrast_fingerprints():
    assert OFFICIAL_BENCHMARK_PROFILE.profile_id == "maeumcall-structured-nlu-v3"
    assert OFFICIAL_BENCHMARK_PROFILE.coverage_contract_payload == (
        OFFICIAL_COVERAGE_CONTRACT_V3.canonical_payload
    )
    assert len(OFFICIAL_COVERAGE_CONTRACT_V3.fingerprint) == 64


def test_positive_contrast_states_are_explicit_live_contract_pairs():
    detailed_keys = {
        scenario_key
        for scenario_key, contract in EVALUATION_CONTRACTS.items()
        if contract.workflow_spec is None
    }
    assert set(DETAILED_POSITIVE_CONTRASTS_V1) == detailed_keys
    positive_families = {
        family.family_id: family
        for family in OFFICIAL_CONTRAST_FAMILIES_V1
        if family.family_id.startswith("positive-vs-unknown-")
    }
    assert len(positive_families) == 16
    for family in positive_families.values():
        positive = next(role for role in family.roles if role.role_id == "positive")
        contract = EVALUATION_CONTRACTS[positive.scenario_key]
        actions_by_state = dict(contract.actions_by_state)
        assert len(positive.allowed_states) == 1
        assert len(positive.allowed_actions) == 1
        state = next(iter(positive.allowed_states))
        assert positive.allowed_actions <= actions_by_state[state]


def test_action_objective_tag_semantics_exactly_cover_live_actions():
    live_actions = set().union(
        *(contract.user_actions for contract in EVALUATION_CONTRACTS.values())
    )
    assert set(ACTION_OBJECTIVE_TAGS_V1) == live_actions
    for contract in EVALUATION_CONTRACTS.values():
        assert dict(contract.objective_tags_by_action) == {
            action: ACTION_OBJECTIVE_TAGS_V1[action] for action in sorted(contract.user_actions)
        }


def test_contrast_manifest_is_order_independent_and_requires_shared_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    family = ContrastFamilyPolicy(
        family_id="appointment-positive-vs-unknown",
        roles=(
            ContrastRolePolicy(
                "positive",
                "교수님:면담 예약",
                frozenset({"provide_appointment_info"}),
                frozenset({"collecting_appointment_info"}),
            ),
            ContrastRolePolicy(
                "unknown",
                "교수님:면담 예약",
                frozenset({"unknown"}),
                frozenset({"collecting_appointment_info", "greeting"}),
            ),
        ),
        shared_context_fields=frozenset(
            {"conversation_state", "current_fields", "offered_alternative_times"}
        ),
    )
    monkeypatch.setattr(
        "evals.structured_nlu.contrast.OFFICIAL_CONTRAST_FAMILIES_V1",
        (family,),
    )
    cases = []
    for split in ("validation", "test"):
        cases.extend(
            (
                _case(
                    case_id=f"appointment.contrast-{split}-positive",
                    message=f"{split} 내일 면담하고 싶습니다.",
                    fields=_appointment_fields(date=ExpectedField(accepted_values=("내일",))),
                    action="provide_appointment_info",
                    tags=("single_field",),
                    split=split,
                ),
                _case(
                    case_id=f"appointment.contrast-{split}-unknown",
                    message=f"{split} 무슨 말인지 모르겠습니다.",
                    fields=_appointment_fields(),
                    action="unknown",
                    tags=("hard_negative",),
                    split=split,
                ),
            )
        )
    dataset = _gold_dataset(*cases)
    groups = []
    for split in ("validation", "test"):
        split_cases = [case for case in cases if case.split.value == split]
        groups.append(
            _approved_contrast_group(
                {
                    "contrast_group_id": f"appointment.{split}",
                    "family_id": family.family_id,
                    "comparison_axis_id": family.family_id,
                    "confusion_axis": "같은 상태에서 정보 제공과 무관 발화를 구분한다.",
                    "members": [
                        {
                            "role_id": "positive"
                            if case.labels.user_action != "unknown"
                            else "unknown",
                            "case_id": case.id,
                            "case_fingerprint": evaluation_case_fingerprint(case),
                        }
                        for case in split_cases
                    ],
                }
            )
        )
    path = tmp_path / "contrast.json"
    payload = {
        "contrast_manifest_schema_version": 1,
        "coverage_contract_id": "maeumcall-structured-nlu-coverage-v3",
        "case_fingerprint_algorithm": "evaluation-case-canonical-json-sha256-v1",
        "groups": copy.deepcopy(groups),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    first = verify_contrast_manifest(dataset, path)

    payload["groups"][0]["definition"]["confusion_axis"] += " 변경"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="approval does not match current content"):
        verify_contrast_manifest(dataset, path)
    payload["groups"][0] = copy.deepcopy(groups[0])

    payload["groups"] = list(reversed(copy.deepcopy(groups)))
    for group in payload["groups"]:
        group["definition"]["members"] = list(reversed(group["definition"]["members"]))
        group["definition"]["confusion_axis"] = unicodedata.normalize(
            "NFD", group["definition"]["confusion_axis"]
        )
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    second = verify_contrast_manifest(dataset, path)
    assert first.fingerprint == second.fingerprint

    stale_group = payload["groups"][0]
    stale_group["definition"]["members"][0]["case_fingerprint"] = "f" * 64
    _refresh_contrast_group_approval(stale_group)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="case fingerprint does not match"):
        verify_contrast_manifest(dataset, path)
    payload["groups"] = list(reversed(copy.deepcopy(groups)))

    tampered_cases = list(dataset.cases)
    target = next(case for case in tampered_cases if case.id.endswith("validation-unknown"))
    target_index = tampered_cases.index(target)
    tampered_cases[target_index] = target.model_copy(update={"conversation_state": "greeting"})
    tampered = tampered_cases[target_index]
    for group in payload["groups"]:
        for member in group["definition"]["members"]:
            if member["case_id"] == tampered.id:
                member["case_fingerprint"] = evaluation_case_fingerprint(tampered)
        _refresh_contrast_group_approval(group)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="share required context"):
        verify_contrast_manifest(
            GoldDataset(
                dataset_version=dataset.dataset_version,
                state_contract_version=dataset.state_contract_version,
                cases=tuple(tampered_cases),
            ),
            path,
        )


def test_qualified_v3_rejects_incomplete_validation_before_test(
    monkeypatch: pytest.MonkeyPatch,
):
    cases = tuple(
        _case(
            case_id=f"appointment.v3-{split}",
            message=f"{split} 면담을 신청합니다.",
            fields=_appointment_fields(date=ExpectedField(accepted_values=(split,))),
            action="provide_appointment_info",
            tags=("single_field",),
            split=split,
        )
        for split in ("development", "validation", "test")
    )
    dataset = _gold_dataset(*cases)
    incomplete = BenchmarkCoverageReport(
        profile_id=OFFICIAL_BENCHMARK_PROFILE.profile_id,
        profile_fingerprint=OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT,
        split=DatasetSplit.VALIDATION,
        case_count=1,
        issues=(
            CoverageIssue(
                dimension=CoverageDimension.SCENARIO,
                missing_values=("예약:병원 예약",),
            ),
        ),
    )
    requested_splits: list[DatasetSplit] = []

    def fake_inspect(_dataset, *, split, profile):
        requested_splits.append(split)
        if split is DatasetSplit.VALIDATION:
            return incomplete
        return BenchmarkCoverageReport(
            profile_id=profile.profile_id,
            profile_fingerprint=profile.fingerprint,
            split=split,
            case_count=1,
            issues=(),
        )

    monkeypatch.setattr(
        "evals.structured_nlu.benchmark.inspect_benchmark_coverage",
        fake_inspect,
    )

    with pytest.raises(ValueError, match="benchmark coverage is incomplete"):
        _prepare_qualified_test_slice(
            dataset,
            authoring_source_fingerprint="a" * 64,
            split_assignment_fingerprint="b" * 64,
            annotation_guideline_fingerprint="c" * 64,
            review_ledger_fingerprint="d" * 64,
            contrast_manifest_fingerprint="e" * 64,
        )
    assert requested_splits == [DatasetSplit.VALIDATION]


def test_profile_rejects_duplicate_states_and_action_union_drift():
    profile = _appointment_test_profile()
    scenario_key, requirement = profile.scenarios[0]
    duplicate_state_requirement = ScenarioCoverageRequirement(
        conversation_states=requirement.conversation_states,
        user_actions=requirement.user_actions,
        fields=requirement.fields,
        change_fields=requirement.change_fields,
        allowed_intents=requirement.allowed_intents,
        actions_by_state=(
            *requirement.actions_by_state,
            requirement.actions_by_state[0],
        ),
        field_options=requirement.field_options,
        scoring_contract_payload=requirement.scoring_contract_payload,
        action_field_present=requirement.action_field_present,
        action_field_absent=requirement.action_field_absent,
    )
    with pytest.raises(ValueError, match="states must be unique"):
        BenchmarkProfile(
            profile_id="duplicate-state-test-v1",
            scenarios=((scenario_key, duplicate_state_requirement),),
            required_tags=profile.required_tags,
        )

    mismatched_actions_requirement = ScenarioCoverageRequirement(
        conversation_states=requirement.conversation_states,
        user_actions=frozenset({"provide_appointment_info"}),
        fields=requirement.fields,
        change_fields=requirement.change_fields,
        allowed_intents=requirement.allowed_intents,
        actions_by_state=requirement.actions_by_state,
        field_options=requirement.field_options,
        scoring_contract_payload=requirement.scoring_contract_payload,
        action_field_present=requirement.action_field_present,
        action_field_absent=requirement.action_field_absent,
    )
    with pytest.raises(ValueError, match="differ from user actions"):
        BenchmarkProfile(
            profile_id="action-union-test-v1",
            scenarios=((scenario_key, mismatched_actions_requirement),),
            required_tags=profile.required_tags,
        )


def test_benchmark_coverage_reports_each_missing_contract_dimension():
    only_case = _case(
        case_id="appointment.incomplete-profile",
        message="진로 상담으로 내일 오후 세 시에 김개굴 이름으로 면담하고 싶습니다.",
        fields=_appointment_fields(
            purpose=ExpectedField(accepted_values=("진로 상담",)),
            date=ExpectedField(accepted_values=("내일",)),
            time=ExpectedField(accepted_values=("오후 세 시",)),
            name=ExpectedField(accepted_values=("김개굴",)),
        ),
        action="provide_appointment_info",
        split="test",
        tags=("multi_field",),
    )

    report = inspect_benchmark_coverage(
        _gold_dataset(only_case),
        split=DatasetSplit.TEST,
        profile=_appointment_test_profile(),
    )

    assert not report.is_complete
    assert {issue.dimension for issue in report.issues} == {
        CoverageDimension.USER_ACTION,
        CoverageDimension.STATE_ACTION,
        CoverageDimension.FIELD_ABSENT,
        CoverageDimension.DIFFICULTY_TAG,
    }


def test_benchmark_requires_same_turn_change_action_and_target_value_pair():
    contract = EVALUATION_CONTRACTS["교수님:면담 예약"]
    profile = BenchmarkProfile(
        profile_id="appointment-inline-change-test-v1",
        scenarios=(
            (
                contract.scenario_key,
                ScenarioCoverageRequirement(
                    conversation_states=frozenset({"confirming_info"}),
                    user_actions=frozenset({"change_date"}),
                    fields=frozenset({"date"}),
                    change_fields=frozenset(),
                    allowed_intents=contract.allowed_intents,
                    actions_by_state=(("confirming_info", frozenset({"change_date"})),),
                    field_options=(),
                    scoring_contract_payload=contract.scoring_contract_payload,
                    action_field_present=frozenset({"change_date->date"}),
                    action_field_absent=frozenset({"change_date->date"}),
                ),
            ),
        ),
        required_tags=frozenset({DifficultyTag.CORRECTION}),
    )
    omitted_replacement = _case(
        case_id="appointment.change-date-without-value",
        message="날짜를 바꾸고 싶습니다.",
        fields=_appointment_fields(),
        action="change_date",
        conversation_state="confirming_info",
        split="test",
        tags=("correction",),
    )

    report = inspect_benchmark_coverage(
        _gold_dataset(omitted_replacement),
        split=DatasetSplit.TEST,
        profile=profile,
    )

    assert CoverageDimension.ACTION_FIELD_PRESENT in {issue.dimension for issue in report.issues}
    assert CoverageDimension.ACTION_FIELD_ABSENT not in {issue.dimension for issue in report.issues}


def test_workflow_absent_coverage_counts_only_the_declared_change_target():
    contract = EVALUATION_CONTRACTS["배달:주문 변경"]
    action_field_present, action_field_absent = contract.action_field_coverage
    profile = BenchmarkProfile(
        profile_id="order-change-clear-target-test-v1",
        scenarios=(
            (
                contract.scenario_key,
                ScenarioCoverageRequirement(
                    conversation_states=frozenset({ORDER_CHANGE_SPEC.confirming_state}),
                    user_actions=frozenset({"change_detail"}),
                    fields=frozenset(ORDER_CHANGE_SPEC.field_keys),
                    change_fields=frozenset(ORDER_CHANGE_SPEC.field_keys),
                    allowed_intents=contract.allowed_intents,
                    actions_by_state=(
                        (ORDER_CHANGE_SPEC.confirming_state, frozenset({"change_detail"})),
                    ),
                    field_options=contract.field_options,
                    scoring_contract_payload=contract.scoring_contract_payload,
                    action_field_present=frozenset(
                        value
                        for value in action_field_present
                        if value.startswith("change_detail->")
                    ),
                    action_field_absent=frozenset(
                        value
                        for value in action_field_absent
                        if value.startswith("change_detail->")
                    ),
                ),
            ),
        ),
        required_tags=frozenset({DifficultyTag.CORRECTION}),
    )
    target = "order_number"
    case = EvaluationCase(
        id="order-change.clear-order-number",
        conversation_group_id="order-change.clear-order-number",
        split="test",
        scenario_key=contract.scenario_key,
        conversation_state=ORDER_CHANGE_SPEC.confirming_state,
        current_fields={
            "order_number": "A-100",
            "change_type": "delivery_address",
            "requested_change": "서울시 새 주소",
            "unavailable_preference": "keep_order",
        },
        offered_alternative_times=(),
        user_message="주문번호를 다시 말할게요.",
        labels=GoldLabels(
            intent=ORDER_CHANGE_SPEC.intent,
            fields={field_name: None for field_name in ORDER_CHANGE_SPEC.field_keys},
            user_action="change_detail",
            change_field=target,
        ),
        tags=("correction",),
        provenance="human_authored",
        review_status="adjudicated",
    )

    report = inspect_benchmark_coverage(
        _gold_dataset(case),
        split=DatasetSplit.TEST,
        profile=profile,
    )
    absence_issue = next(
        issue for issue in report.issues if issue.dimension is CoverageDimension.ACTION_FIELD_ABSENT
    )

    assert "change_detail->order_number" not in absence_issue.missing_values
    assert "change_detail->requested_change" in absence_issue.missing_values


def test_prepare_benchmark_slice_requires_test_coverage_and_adjudication():
    present_case = _case(
        case_id="appointment.complete-present",
        message="진로 상담으로 내일 오후 세 시에 김개굴 이름으로 면담하고 싶습니다.",
        fields=_appointment_fields(
            purpose=ExpectedField(accepted_values=("진로 상담",)),
            date=ExpectedField(accepted_values=("내일",)),
            time=ExpectedField(accepted_values=("오후 세 시",)),
            name=ExpectedField(accepted_values=("김개굴",)),
        ),
        action="provide_appointment_info",
        split="test",
        tags=("multi_field",),
    )
    absent_case = _case(
        case_id="appointment.complete-absent",
        message="잘 모르겠습니다.",
        fields=_appointment_fields(),
        action="unknown",
        split="test",
        tags=("hard_negative",),
    )
    single_field_case = _case(
        case_id="appointment.complete-single-field",
        message="내일로 부탁드립니다.",
        fields=_appointment_fields(
            date=ExpectedField(accepted_values=("내일",)),
        ),
        action="provide_appointment_info",
        split="test",
        tags=("single_field",),
    )
    dataset = _gold_dataset(present_case, absent_case, single_field_case)

    benchmark = prepare_benchmark_slice(
        dataset,
        split=DatasetSplit.TEST,
        profile=_appointment_test_profile(),
    )

    assert benchmark.split is DatasetSplit.TEST
    assert benchmark.coverage.is_complete
    assert benchmark.cases == (present_case, absent_case, single_field_case)

    with pytest.raises(ValueError, match="requires a complete corpus"):
        _prepare_qualified_test_slice(
            dataset,
            authoring_source_fingerprint="a" * 64,
            split_assignment_fingerprint="b" * 64,
            annotation_guideline_fingerprint="c" * 64,
            review_ledger_fingerprint="d" * 64,
            contrast_manifest_fingerprint="e" * 64,
        )

    forged_qualified_slice = QualifiedTestSlice(
        **benchmark.__dict__,
        validation_coverage=benchmark.coverage,
        coverage_contract_fingerprint=OFFICIAL_COVERAGE_CONTRACT_V3.fingerprint,
        contrast_manifest_fingerprint="e" * 64,
        authoring_source_fingerprint="a" * 64,
        split_assignment_fingerprint="b" * 64,
        annotation_guideline_fingerprint="c" * 64,
        review_ledger_fingerprint="d" * 64,
        corpus_fingerprint="not-used-before-profile-validation",
        corpus_cases=dataset.cases,
    )
    with pytest.raises(ValueError, match="qualified test profile id does not match"):
        _score_qualified_test_slice(forged_qualified_slice, ())

    mixed_split = QualifiedTestSlice(
        profile_id=OFFICIAL_BENCHMARK_PROFILE.profile_id,
        profile_fingerprint=OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT,
        dataset_version=dataset.dataset_version,
        state_contract_version=dataset.state_contract_version,
        dataset_fingerprint=benchmark.dataset_fingerprint,
        split=DatasetSplit.TEST,
        cases=(
            present_case.model_copy(update={"split": DatasetSplit.DEVELOPMENT}),
            absent_case,
        ),
        coverage=benchmark.coverage,
        validation_coverage=benchmark.coverage,
        coverage_contract_fingerprint=OFFICIAL_COVERAGE_CONTRACT_V3.fingerprint,
        contrast_manifest_fingerprint="e" * 64,
        authoring_source_fingerprint="a" * 64,
        split_assignment_fingerprint="b" * 64,
        annotation_guideline_fingerprint="c" * 64,
        review_ledger_fingerprint="d" * 64,
        corpus_fingerprint="not-used-before-split-validation",
        corpus_cases=dataset.cases,
    )
    with pytest.raises(ValueError, match="contains a non-test case"):
        _score_qualified_test_slice(mixed_split, ())


@pytest.mark.parametrize("invalid_fingerprint", ("B" * 64, "b" * 63))
def test_qualified_split_assignment_fingerprint_must_be_lowercase_sha256(
    invalid_fingerprint: str,
):
    test_case = _case(
        case_id="appointment.invalid-split-fingerprint",
        message="내일 면담하고 싶습니다.",
        fields=_appointment_fields(date=ExpectedField(accepted_values=("내일",))),
        action="provide_appointment_info",
        split="test",
        tags=("single_field",),
    )
    dataset = _gold_dataset(test_case)

    with pytest.raises(ValueError, match="split assignment fingerprint"):
        _prepare_qualified_test_slice(
            dataset,
            authoring_source_fingerprint="a" * 64,
            split_assignment_fingerprint=invalid_fingerprint,
            annotation_guideline_fingerprint="c" * 64,
            review_ledger_fingerprint="d" * 64,
            contrast_manifest_fingerprint="e" * 64,
        )

    coverage = inspect_benchmark_coverage(
        dataset,
        split=DatasetSplit.TEST,
        profile=_appointment_test_profile(),
    )
    forged = QualifiedTestSlice(
        profile_id=OFFICIAL_BENCHMARK_PROFILE.profile_id,
        profile_fingerprint=OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT,
        dataset_version=dataset.dataset_version,
        state_contract_version=dataset.state_contract_version,
        dataset_fingerprint="not-reached-before-fingerprint-validation",
        split=DatasetSplit.TEST,
        cases=dataset.cases,
        coverage=coverage,
        validation_coverage=coverage,
        coverage_contract_fingerprint=OFFICIAL_COVERAGE_CONTRACT_V3.fingerprint,
        contrast_manifest_fingerprint="e" * 64,
        authoring_source_fingerprint="a" * 64,
        split_assignment_fingerprint=invalid_fingerprint,
        annotation_guideline_fingerprint="c" * 64,
        review_ledger_fingerprint="d" * 64,
        corpus_fingerprint="not-reached-before-fingerprint-validation",
        corpus_cases=dataset.cases,
    )
    with pytest.raises(ValueError, match="split assignment fingerprint"):
        _score_qualified_test_slice(forged, ())


def test_benchmark_coverage_rejects_unadjudicated_test_case():
    draft_case = _case(
        case_id="appointment.unapproved-test-case",
        message="잘 모르겠습니다.",
        fields=_appointment_fields(),
        action="unknown",
        review_status="reviewed",
        split="test",
        tags=("hard_negative",),
    )

    report = inspect_benchmark_coverage(
        _gold_dataset(draft_case),
        split=DatasetSplit.TEST,
        profile=_appointment_test_profile(),
    )

    assert CoverageDimension.REVIEW_STATUS in {issue.dimension for issue in report.issues}


def test_qualified_scoring_rejects_a_tampered_complete_corpus():
    test_case = _case(
        case_id="appointment.corpus-test",
        message="내일 면담하고 싶습니다.",
        fields=_appointment_fields(
            date=ExpectedField(accepted_values=("내일",)),
        ),
        action="provide_appointment_info",
        split="test",
        tags=("single_field",),
    )
    development_case = _case(
        case_id="appointment.corpus-development",
        message="모레 면담하고 싶습니다.",
        fields=_appointment_fields(
            date=ExpectedField(accepted_values=("모레",)),
        ),
        action="provide_appointment_info",
        tags=("single_field",),
    )
    validation_case = _case(
        case_id="appointment.corpus-validation",
        message="다음 주에 면담하고 싶습니다.",
        fields=_appointment_fields(
            date=ExpectedField(accepted_values=("다음 주",)),
        ),
        action="provide_appointment_info",
        split="validation",
        tags=("single_field",),
    )
    corpus = _gold_dataset(development_case, validation_case, test_case)
    custom_report = inspect_benchmark_coverage(
        corpus,
        split=DatasetSplit.TEST,
        profile=_appointment_test_profile(),
    )
    forged_slice = QualifiedTestSlice(
        profile_id=OFFICIAL_BENCHMARK_PROFILE.profile_id,
        profile_fingerprint=OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT,
        dataset_version=corpus.dataset_version,
        state_contract_version=corpus.state_contract_version,
        dataset_fingerprint="forged-test-fingerprint",
        split=DatasetSplit.TEST,
        cases=(test_case,),
        coverage=custom_report,
        validation_coverage=custom_report,
        coverage_contract_fingerprint=OFFICIAL_COVERAGE_CONTRACT_V3.fingerprint,
        contrast_manifest_fingerprint="e" * 64,
        authoring_source_fingerprint="a" * 64,
        split_assignment_fingerprint="b" * 64,
        annotation_guideline_fingerprint="c" * 64,
        review_ledger_fingerprint="d" * 64,
        corpus_fingerprint="forged-corpus-fingerprint",
        corpus_cases=corpus.cases,
    )

    with pytest.raises(ValueError, match="corpus fingerprint does not match"):
        _score_qualified_test_slice(forged_slice, ())


def test_development_split_supports_custom_checks_but_not_qualified_scoring():
    present_case = _case(
        case_id="appointment.development-present",
        message="진로 상담으로 내일 오후 세 시에 김개굴 이름으로 면담하고 싶습니다.",
        fields=_appointment_fields(
            purpose=ExpectedField(accepted_values=("진로 상담",)),
            date=ExpectedField(accepted_values=("내일",)),
            time=ExpectedField(accepted_values=("오후 세 시",)),
            name=ExpectedField(accepted_values=("김개굴",)),
        ),
        action="provide_appointment_info",
        tags=("multi_field",),
    )
    absent_case = _case(
        case_id="appointment.development-absent",
        message="잘 모르겠습니다.",
        fields=_appointment_fields(),
        action="unknown",
        tags=("hard_negative",),
    )
    single_field_case = _case(
        case_id="appointment.development-single-field",
        message="내일로 부탁드립니다.",
        fields=_appointment_fields(
            date=ExpectedField(accepted_values=("내일",)),
        ),
        action="provide_appointment_info",
        tags=("single_field",),
    )
    dataset = _gold_dataset(present_case, absent_case, single_field_case)

    benchmark = prepare_benchmark_slice(
        dataset,
        split=DatasetSplit.DEVELOPMENT,
        profile=_appointment_test_profile(),
    )

    assert benchmark.coverage.is_complete
    assert benchmark.split is DatasetSplit.DEVELOPMENT
    forged_qualified_slice = QualifiedTestSlice(
        **benchmark.__dict__,
        validation_coverage=benchmark.coverage,
        coverage_contract_fingerprint=OFFICIAL_COVERAGE_CONTRACT_V3.fingerprint,
        contrast_manifest_fingerprint="e" * 64,
        authoring_source_fingerprint="a" * 64,
        split_assignment_fingerprint="b" * 64,
        annotation_guideline_fingerprint="c" * 64,
        review_ledger_fingerprint="d" * 64,
        corpus_fingerprint="not-used-before-split-validation",
        corpus_cases=dataset.cases,
    )
    with pytest.raises(ValueError, match="qualified scoring requires the test split"):
        _score_qualified_test_slice(forged_qualified_slice, ())
    with pytest.raises(ValueError, match="requires a complete corpus"):
        _prepare_qualified_test_slice(
            dataset,
            authoring_source_fingerprint="a" * 64,
            split_assignment_fingerprint="b" * 64,
            annotation_guideline_fingerprint="c" * 64,
            review_ledger_fingerprint="d" * 64,
            contrast_manifest_fingerprint="e" * 64,
        )


def test_metrics_count_change_field_on_detailed_extractor_as_contract_failure():
    case = _case(
        case_id="appointment.invalid-change-field",
        message="내일 면담 가능할까요?",
        fields=_appointment_fields(date=ExpectedField(accepted_values=("내일",))),
        action="provide_appointment_info",
        tags=("single_field",),
    )
    prediction = _prediction(
        case.id,
        fields={
            "appointment_purpose": None,
            "date": "내일",
            "time": None,
            "user_name": None,
        },
        action="provide_appointment_info",
        change_field="not-a-real-field",
    )

    scores = score_predictions((case,), (prediction,))

    assert scores.first_attempt_contract_success_rate == 0.0
    assert scores.final_contract_success_rate == 0.0


def test_metrics_count_workflow_option_outside_live_contract_as_contract_failure():
    case = EvaluationCase(
        id="delivery.invalid-option",
        conversation_group_id="delivery.invalid-option",
        split="development",
        scenario_key="배달:주문 변경",
        conversation_state="collecting_order_change",
        current_fields={
            "order_number": None,
            "change_type": None,
            "requested_change": None,
            "unavailable_preference": None,
        },
        offered_alternative_times=(),
        user_message="배송지를 바꾸고 싶어요.",
        labels=GoldLabels(
            intent="delivery_order_change",
            fields={
                "order_number": None,
                "change_type": ExpectedField(accepted_values=("delivery_address",)),
                "requested_change": None,
                "unavailable_preference": None,
            },
            user_action="provide_details",
            change_field=None,
        ),
        tags=("single_field",),
        provenance="human_authored",
        review_status="adjudicated",
    )
    prediction = _prediction(
        case.id,
        intent="delivery_order_change",
        fields={
            "order_number": None,
            "change_type": "not-a-real-option",
            "requested_change": None,
            "unavailable_preference": None,
        },
        action="provide_details",
    )

    scores = score_predictions((case,), (prediction,))

    assert scores.first_attempt_contract_success_rate == 0.0
    assert scores.final_contract_success_rate == 0.0
    assert scores.counts.gold_present_slots == 0
