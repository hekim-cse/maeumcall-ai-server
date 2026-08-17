from __future__ import annotations

from copy import deepcopy

import pytest

from services.flow.common.state_contract import ScenarioStateContractError
from services.flow.professor.absence.response import (
    PROFESSOR_ABSENCE_CONTRACT,
    PROFESSOR_ABSENCE_STATE_CONTRACT,
)
from services.flow.professor.appointment.response import (
    PROFESSOR_APPOINTMENT_CONTRACT,
    PROFESSOR_APPOINTMENT_STATE_CONTRACT,
)
from services.flow.professor.assignment.response import (
    PROFESSOR_ASSIGNMENT_CONTRACT,
    PROFESSOR_ASSIGNMENT_STATE_CONTRACT,
)
from services.flow.reservation.hair_salon.response import (
    HAIR_SALON_RESERVATION_CONTRACT,
    HAIR_SALON_STATE_CONTRACT,
)
from services.flow.reservation.hospital.response import (
    HOSPITAL_RESERVATION_CONTRACT,
    HOSPITAL_STATE_CONTRACT,
)
from services.flow.reservation.restaurant.response import (
    RESTAURANT_RESERVATION_CONTRACT,
    RESTAURANT_STATE_CONTRACT,
)
from services.flow.reservation.study_room.response import (
    STUDY_ROOM_RESERVATION_CONTRACT,
    STUDY_ROOM_STATE_CONTRACT,
)


pytestmark = pytest.mark.unit


RESERVATION_CONTRACTS = (
    HOSPITAL_STATE_CONTRACT,
    RESTAURANT_STATE_CONTRACT,
    HAIR_SALON_STATE_CONTRACT,
    STUDY_ROOM_STATE_CONTRACT,
)
PROFESSOR_CONTRACTS = (
    PROFESSOR_APPOINTMENT_STATE_CONTRACT,
    PROFESSOR_ASSIGNMENT_STATE_CONTRACT,
    PROFESSOR_ABSENCE_STATE_CONTRACT,
)
DETAILED_CONTRACTS = (
    HOSPITAL_RESERVATION_CONTRACT,
    RESTAURANT_RESERVATION_CONTRACT,
    HAIR_SALON_RESERVATION_CONTRACT,
    STUDY_ROOM_RESERVATION_CONTRACT,
    PROFESSOR_APPOINTMENT_CONTRACT,
    PROFESSOR_ASSIGNMENT_CONTRACT,
    PROFESSOR_ABSENCE_CONTRACT,
)


def test_all_existing_detailed_graphs_apply_a_domain_state_validator():
    assert all(contract.validate_state is not None for contract in DETAILED_CONTRACTS)


@pytest.mark.parametrize("contract", RESERVATION_CONTRACTS)
def test_reservation_contract_accepts_a_complete_collecting_state(contract):
    state = _reservation_state(contract)

    contract.validate(state)


@pytest.mark.parametrize("contract", PROFESSOR_CONTRACTS)
def test_professor_contract_accepts_a_consistent_collecting_state(contract):
    state = _professor_state(contract)

    contract.validate(state)


@pytest.mark.parametrize("contract", (*RESERVATION_CONTRACTS, *PROFESSOR_CONTRACTS))
def test_detailed_contract_rejects_an_unknown_action(contract):
    state = (
        _reservation_state(contract)
        if contract in RESERVATION_CONTRACTS
        else _professor_state(contract)
    )
    state["user_action"] = "client_defined_action"

    with pytest.raises(ScenarioStateContractError) as exc_info:
        contract.validate(state)

    assert exc_info.value.code == "SCENARIO_STATE_INVALID"


def test_reservation_contract_rejects_confirmation_without_required_fields():
    state = _reservation_state(HOSPITAL_STATE_CONTRACT)
    state.update(
        {
            "conversation_state": "reservation_confirmed",
            "department": None,
            "selected_time": "오후 3시",
            "reservation_confirmed": True,
        }
    )

    with pytest.raises(ScenarioStateContractError):
        HOSPITAL_STATE_CONTRACT.validate(state)


def test_reservation_contract_rejects_an_incoherent_availability_result():
    state = _reservation_state(RESTAURANT_STATE_CONTRACT)
    state.update(
        {
            "conversation_state": "reservation_available",
            "availability_status": "available",
            "availability_reason": "해당 시간은 이미 마감되었습니다.",
            "available_time": None,
        }
    )

    with pytest.raises(ScenarioStateContractError):
        RESTAURANT_STATE_CONTRACT.validate(state)


def test_reservation_contract_returns_a_typed_error_for_non_string_alternatives():
    state = _reservation_state(STUDY_ROOM_STATE_CONTRACT)
    state["alternative_times"] = [{"time": "오후 3시"}]

    with pytest.raises(ScenarioStateContractError):
        STUDY_ROOM_STATE_CONTRACT.validate(state)


def test_professor_contract_rejects_a_missing_field_list_that_hides_missing_data():
    state = _professor_state(PROFESSOR_ASSIGNMENT_STATE_CONTRACT)
    state["missing_fields"] = []

    with pytest.raises(ScenarioStateContractError):
        PROFESSOR_ASSIGNMENT_STATE_CONTRACT.validate(state)


def test_professor_contract_returns_a_typed_error_for_non_string_missing_fields():
    state = _professor_state(PROFESSOR_ABSENCE_STATE_CONTRACT)
    state["missing_fields"] = [{"field": "class_name"}]

    with pytest.raises(ScenarioStateContractError):
        PROFESSOR_ABSENCE_STATE_CONTRACT.validate(state)


def _reservation_state(contract) -> dict:
    state = {field: None for field in contract.expected_fields}
    state.update(
        {
            "intent": next(
                intent for intent in contract.allowed_intents if intent is not None
            ),
            contract.identity_field: "서비스",
            "conversation_state": "greeting",
            "last_ai_message": "무엇을 도와드릴까요?",
            "user_action": "unknown",
            "alternative_times": [],
            "reservation_confirmed": False,
        }
    )
    return deepcopy(state)


def _professor_state(contract) -> dict:
    state = {field: None for field in contract.expected_fields}
    state.update(
        {
            "intent": contract.intent,
            "professor_name": "교수님",
            "conversation_state": "greeting",
            "missing_fields": list(contract.required_fields),
            "last_ai_message": "무엇을 도와드릴까요?",
            "user_action": "unknown",
        }
    )
    return deepcopy(state)
