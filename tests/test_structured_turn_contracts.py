import pytest

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from llm.structured_output import (
    ActionFieldRule,
    action_field_rules_json_for_state,
    apply_action_field_delta,
    build_action_field_contract,
    validate_action_field_delta,
)
from services.flow.cityhall.contracts import (
    BULKY_WASTE_SPEC,
    PASSPORT_SPEC,
    RESIDENT_CERTIFICATE_SPEC,
)
from services.flow.delivery.contracts import (
    DELIVERY_DELAY_SPEC,
    ORDER_CHANGE_SPEC,
    REFUND_REDELIVERY_SPEC,
)
from services.flow.professor.absence.llm_structured import (
    PROFESSOR_ABSENCE_ACTION_FIELD_CONTRACT,
    PROFESSOR_ABSENCE_FIELD_NAMES,
)
from services.flow.professor.appointment.llm_structured import (
    PROFESSOR_APPOINTMENT_ACTION_FIELD_CONTRACT,
    PROFESSOR_APPOINTMENT_FIELD_NAMES,
)
from services.flow.professor.assignment.llm_structured import (
    PROFESSOR_ASSIGNMENT_ACTION_FIELD_CONTRACT,
    PROFESSOR_ASSIGNMENT_FIELD_NAMES,
)
from services.flow.reservation.hair_salon.llm_structured import (
    HAIR_SALON_ACTION_FIELD_CONTRACT,
    HAIR_SALON_FIELD_NAMES,
)
from services.flow.reservation.hospital.llm_structured import (
    HOSPITAL_ACTION_FIELD_CONTRACT,
    HOSPITAL_FIELD_NAMES,
)
from services.flow.reservation.restaurant.llm_structured import (
    RESTAURANT_ACTION_FIELD_CONTRACT,
    RESTAURANT_FIELD_NAMES,
)
from services.flow.reservation.study_room.llm_structured import (
    STUDY_ROOM_ACTION_FIELD_CONTRACT,
    STUDY_ROOM_FIELD_NAMES,
)
from services.flow.service_workflow.structured_contract import (
    validate_service_workflow_turn_delta,
)
from services.flow.support.contracts import (
    NETWORK_CALL_SPEC,
    PLAN_CONTRACT_SPEC,
    SERVICE_REQUEST_SPEC,
)

DETAILED_TURN_CONTRACTS = (
    ("hospital", HOSPITAL_FIELD_NAMES, HOSPITAL_ACTION_FIELD_CONTRACT),
    ("restaurant", RESTAURANT_FIELD_NAMES, RESTAURANT_ACTION_FIELD_CONTRACT),
    ("hair_salon", HAIR_SALON_FIELD_NAMES, HAIR_SALON_ACTION_FIELD_CONTRACT),
    ("study_room", STUDY_ROOM_FIELD_NAMES, STUDY_ROOM_ACTION_FIELD_CONTRACT),
    (
        "professor_appointment",
        PROFESSOR_APPOINTMENT_FIELD_NAMES,
        PROFESSOR_APPOINTMENT_ACTION_FIELD_CONTRACT,
    ),
    (
        "professor_assignment",
        PROFESSOR_ASSIGNMENT_FIELD_NAMES,
        PROFESSOR_ASSIGNMENT_ACTION_FIELD_CONTRACT,
    ),
    (
        "professor_absence",
        PROFESSOR_ABSENCE_FIELD_NAMES,
        PROFESSOR_ABSENCE_ACTION_FIELD_CONTRACT,
    ),
)

WORKFLOW_SPECS = (
    ORDER_CHANGE_SPEC,
    DELIVERY_DELAY_SPEC,
    REFUND_REDELIVERY_SPEC,
    PASSPORT_SPEC,
    RESIDENT_CERTIFICATE_SPEC,
    BULKY_WASTE_SPEC,
    NETWORK_CALL_SPEC,
    PLAN_CONTRACT_SPEC,
    SERVICE_REQUEST_SPEC,
)


@pytest.mark.parametrize(("name", "field_names", "contract"), DETAILED_TURN_CONTRACTS)
def test_detailed_contracts_reject_every_action_field_contradiction(
    name,
    field_names,
    contract,
):
    del name
    ordered_fields = sorted(field_names)
    for action, rule in contract.items():
        empty_fields = {field: None for field in field_names}
        if rule.required_fields or rule.require_any:
            with pytest.raises(ValueError):
                validate_action_field_delta(
                    empty_fields,
                    user_action=action,
                    contract=contract,
                )

        if rule.allowed_fields:
            allowed_field = sorted(rule.allowed_fields)[0]
            valid_fields = dict(empty_fields)
            valid_fields[allowed_field] = "현재 발화에서 확인된 값"
            validate_action_field_delta(
                valid_fields,
                user_action=action,
                contract=contract,
            )

        forbidden_fields = [field for field in ordered_fields if field not in rule.allowed_fields]
        if forbidden_fields:
            invalid_fields = dict(empty_fields)
            invalid_fields[forbidden_fields[0]] = "행동과 모순되는 값"
            with pytest.raises(ValueError, match="must not include"):
                validate_action_field_delta(
                    invalid_fields,
                    user_action=action,
                    contract=contract,
                )


@pytest.mark.parametrize("spec", WORKFLOW_SPECS, ids=lambda spec: spec.graph_name)
def test_workflow_contracts_reject_control_actions_with_field_deltas(spec):
    empty_fields = {key: None for key in spec.field_keys}
    current_fields = {key: None for key in spec.field_keys}
    first_field = spec.field_keys[0]
    conflicting_fields = dict(empty_fields)
    conflicting_fields[first_field] = _valid_workflow_value(spec, first_field)

    control_actions = spec.user_actions - {"provide_details", "change_detail"}
    for action in control_actions:
        with pytest.raises(ValueError, match="must not include"):
            validate_service_workflow_turn_delta(
                spec,
                fields=conflicting_fields,
                current_fields=current_fields,
                user_action=action,
                change_field=None,
            )

    with pytest.raises(ValueError, match="at least one"):
        validate_service_workflow_turn_delta(
            spec,
            fields=empty_fields,
            current_fields=current_fields,
            user_action="provide_details",
            change_field=None,
        )


@pytest.mark.parametrize("spec", WORKFLOW_SPECS, ids=lambda spec: spec.graph_name)
def test_workflow_change_detail_can_change_only_its_declared_field(spec):
    target, unrelated = spec.field_keys[:2]
    current_fields = {key: None for key in spec.field_keys}
    current_fields[target] = _valid_workflow_value(spec, target)
    fields = {key: None for key in spec.field_keys}
    fields[target] = _different_workflow_value(spec, target, current_fields[target])
    validate_service_workflow_turn_delta(
        spec,
        fields=fields,
        current_fields=current_fields,
        user_action="change_detail",
        change_field=target,
    )

    fields[unrelated] = _valid_workflow_value(spec, unrelated)
    with pytest.raises(ValueError, match="only the field"):
        validate_service_workflow_turn_delta(
            spec,
            fields=fields,
            current_fields=current_fields,
            user_action="change_detail",
            change_field=target,
        )


@pytest.mark.parametrize("spec", WORKFLOW_SPECS, ids=lambda spec: spec.graph_name)
def test_workflow_greeting_does_not_offer_change_detail(spec):
    assert "change_detail" not in spec.actions_by_state["greeting"]


@pytest.mark.parametrize("spec", WORKFLOW_SPECS, ids=lambda spec: spec.graph_name)
def test_workflow_provide_accepts_only_previously_missing_fields(spec):
    target = spec.field_keys[0]
    current_fields = {key: None for key in spec.field_keys}
    value = _valid_workflow_value(spec, target)
    fields = {key: None for key in spec.field_keys}
    fields[target] = value

    validate_service_workflow_turn_delta(
        spec,
        fields=fields,
        current_fields=current_fields,
        user_action="provide_details",
        change_field=None,
    )
    current_fields[target] = value
    with pytest.raises(ValueError, match="only fields missing"):
        validate_service_workflow_turn_delta(
            spec,
            fields=fields,
            current_fields=current_fields,
            user_action="provide_details",
            change_field=None,
        )


@pytest.mark.parametrize("spec", WORKFLOW_SPECS, ids=lambda spec: spec.graph_name)
def test_workflow_change_requires_an_existing_value_and_a_real_replacement(spec):
    target = spec.field_keys[0]
    empty_current = {key: None for key in spec.field_keys}
    fields = {key: None for key in spec.field_keys}
    fields[target] = _valid_workflow_value(spec, target)

    with pytest.raises(ValueError, match="previously collected"):
        validate_service_workflow_turn_delta(
            spec,
            fields=fields,
            current_fields=empty_current,
            user_action="change_detail",
            change_field=target,
        )

    current_fields = dict(empty_current)
    current_fields[target] = fields[target]
    with pytest.raises(ValueError, match="new value"):
        validate_service_workflow_turn_delta(
            spec,
            fields=fields,
            current_fields=current_fields,
            user_action="change_detail",
            change_field=target,
        )


@pytest.mark.parametrize(
    "scenario_key",
    ("예약:병원 예약", "예약:식당 예약", "예약:미용실 예약", "예약:스터디룸 예약"),
)
def test_reservation_evaluation_contract_requires_exact_server_alternative(scenario_key):
    contract = EVALUATION_CONTRACTS[scenario_key]
    conversation_state = sorted(contract.alternative_states)[0]
    fields = {name: None for name in contract.field_names}
    fields["selected_time"] = "오후 4시"
    intent = "reservation"

    contract.validate_prediction(
        intent=intent,
        fields=fields,
        user_action="select_alternative_time",
        change_field=None,
        conversation_state=conversation_state,
        offered_alternative_times=("오후 4시",),
    )
    with pytest.raises(ValueError, match="exactly match"):
        contract.validate_prediction(
            intent=intent,
            fields=fields,
            user_action="select_alternative_time",
            change_field=None,
            conversation_state=conversation_state,
            offered_alternative_times=("오 후 4 시",),
        )


def test_field_reducer_preserves_replacement_and_clears_omitted_change_target():
    current = {"date": "내일", "time": "오후 2시"}

    replaced = apply_action_field_delta(
        current,
        {"date": "모레", "time": None},
        user_action="change_date",
        change_targets={"change_date": "date"},
    )
    cleared = apply_action_field_delta(
        current,
        {"date": None, "time": None},
        user_action="change_date",
        change_targets={"change_date": "date"},
    )

    assert replaced == {"date": "모레", "time": "오후 2시"}
    assert cleared == {"date": None, "time": "오후 2시"}


def test_prompt_rules_are_serialized_from_the_same_validator_contract():
    serialized = action_field_rules_json_for_state(
        "confirming_info",
        allowed_by_state={"confirming_info": frozenset({"confirm", "change_date"})},
        contract={
            "confirm": ActionFieldRule(),
            "change_date": ActionFieldRule(allowed_fields=frozenset({"date"})),
        },
    )

    assert '"confirm": {"allowed_fields": []' in serialized
    assert '"change_date": {"allowed_fields": ["date"]' in serialized


def test_contract_builder_rejects_impossible_require_any_rule():
    with pytest.raises(ValueError, match="requires a field but allows none"):
        build_action_field_contract(
            field_names={"date"},
            user_actions={"provide"},
            rules={"provide": ActionFieldRule(require_any=True)},
        )


def _valid_workflow_value(spec, field_name):
    field = next(field for field in spec.fields if field.key == field_name)
    return field.options[0].value if field.options else "검증된 값"


def _different_workflow_value(spec, field_name, current_value):
    field = next(field for field in spec.fields if field.key == field_name)
    if field.options:
        return next(option.value for option in field.options if option.value != current_value)
    return f"{current_value} 변경"
