from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from services.flow.cityhall.contracts import (
    BULKY_WASTE_SPEC,
    PASSPORT_SPEC,
    RESIDENT_CERTIFICATE_SPEC,
)
from services.flow.common.state_contract import build_scenario_key
from services.flow.delivery.contracts import (
    DELIVERY_DELAY_SPEC,
    ORDER_CHANGE_SPEC,
    REFUND_REDELIVERY_SPEC,
)
from services.flow.professor.absence.llm_structured import (
    DEFAULT_ABSENCE_STRUCTURED_RESULT,
    PROFESSOR_ABSENCE_USER_ACTIONS,
)
from services.flow.professor.absence.response import PROFESSOR_ABSENCE_CONTRACT
from services.flow.professor.appointment.llm_structured import (
    DEFAULT_APPOINTMENT_STRUCTURED_RESULT,
    PROFESSOR_APPOINTMENT_USER_ACTIONS,
)
from services.flow.professor.appointment.response import PROFESSOR_APPOINTMENT_CONTRACT
from services.flow.professor.assignment.llm_structured import (
    DEFAULT_ASSIGNMENT_STRUCTURED_RESULT,
    PROFESSOR_ASSIGNMENT_USER_ACTIONS,
)
from services.flow.professor.assignment.response import PROFESSOR_ASSIGNMENT_CONTRACT
from services.flow.reservation.hair_salon.llm_structured import (
    DEFAULT_HAIR_SALON_STRUCTURED_RESULT,
    HAIR_SALON_USER_ACTIONS,
)
from services.flow.reservation.hair_salon.response import HAIR_SALON_RESERVATION_CONTRACT
from services.flow.reservation.hospital.llm_structured import (
    DEFAULT_HOSPITAL_STRUCTURED_RESULT,
    HOSPITAL_USER_ACTIONS,
)
from services.flow.reservation.hospital.response import HOSPITAL_RESERVATION_CONTRACT
from services.flow.reservation.restaurant.llm_structured import (
    DEFAULT_RESTAURANT_STRUCTURED_RESULT,
    RESTAURANT_USER_ACTIONS,
)
from services.flow.reservation.restaurant.response import RESTAURANT_RESERVATION_CONTRACT
from services.flow.reservation.study_room.llm_structured import (
    DEFAULT_STUDY_ROOM_STRUCTURED_RESULT,
    STUDY_ROOM_USER_ACTIONS,
)
from services.flow.reservation.study_room.response import STUDY_ROOM_RESERVATION_CONTRACT
from services.flow.service_workflow.contracts import WORKFLOW_ACTIONS, ServiceWorkflowSpec
from services.flow.support.contracts import (
    NETWORK_CALL_SPEC,
    PLAN_CONTRACT_SPEC,
    SERVICE_REQUEST_SPEC,
)


@dataclass(frozen=True)
class EvaluationContract:
    scenario_key: str
    allowed_intents: frozenset[str | None]
    field_names: tuple[str, ...]
    conversation_states: frozenset[str]
    user_actions: frozenset[str]
    uses_current_fields: bool
    field_options: tuple[tuple[str, frozenset[str]], ...] = ()

    def validate_prediction(
        self,
        *,
        intent: str | None,
        fields: dict[str, str | None],
        user_action: str,
        change_field: str | None,
    ) -> None:
        """Validate normalized model output against the live scenario contract."""
        if set(fields) != set(self.field_names):
            raise ValueError(
                f"prediction fields do not match {self.scenario_key}: {sorted(fields)}"
            )
        if intent not in self.allowed_intents:
            raise ValueError(f"prediction intent is not allowed for {self.scenario_key}: {intent}")
        if user_action not in self.user_actions:
            raise ValueError(
                f"prediction user_action is not allowed for {self.scenario_key}: {user_action}"
            )

        for field_name, allowed_values in self.field_options:
            value = fields[field_name]
            if value is not None and value not in allowed_values:
                raise ValueError(
                    f"prediction {field_name} is not allowed for {self.scenario_key}: {value}"
                )

        if self.uses_current_fields:
            if user_action == "change_detail":
                if change_field not in self.field_names:
                    raise ValueError("change_field must name a workflow field")
            elif change_field is not None:
                raise ValueError("change_field must be null unless user_action is change_detail")
        elif change_field is not None:
            raise ValueError("change_field is only used by service workflows")


def _detailed_contract(
    *,
    category: str,
    title: str,
    default_result: dict[str, object],
    conversation_states: frozenset[str],
    user_actions: frozenset[str],
    allowed_intents: frozenset[str | None] | None = None,
) -> EvaluationContract:
    field_names = tuple(key for key in default_result if key not in {"intent", "user_action"})
    default_intent = default_result.get("intent")
    resolved_intents = allowed_intents or frozenset({default_intent})
    if not resolved_intents or any(
        intent is not None and (not isinstance(intent, str) or not intent)
        for intent in resolved_intents
    ):
        raise RuntimeError(f"evaluation intents are invalid: {category}:{title}")
    return EvaluationContract(
        scenario_key=build_scenario_key(category, title),
        allowed_intents=resolved_intents,
        field_names=field_names,
        conversation_states=conversation_states - {"END"},
        user_actions=user_actions,
        uses_current_fields=False,
    )


def _workflow_contract(spec: ServiceWorkflowSpec) -> EvaluationContract:
    return EvaluationContract(
        scenario_key=build_scenario_key(spec.category, spec.title),
        allowed_intents=frozenset({spec.intent}),
        field_names=spec.field_keys,
        conversation_states=spec.allowed_conversation_states - {"END"},
        user_actions=WORKFLOW_ACTIONS,
        uses_current_fields=True,
        field_options=tuple(
            (field.key, frozenset(option.value for option in field.options))
            for field in spec.fields
            if field.options
        ),
    )


_CONTRACTS = (
    _detailed_contract(
        category="예약",
        title="병원 예약",
        default_result=DEFAULT_HOSPITAL_STRUCTURED_RESULT,
        conversation_states=HOSPITAL_RESERVATION_CONTRACT.allowed_conversation_states,
        user_actions=HOSPITAL_USER_ACTIONS,
        allowed_intents=frozenset({"reservation", None}),
    ),
    _detailed_contract(
        category="예약",
        title="식당 예약",
        default_result=DEFAULT_RESTAURANT_STRUCTURED_RESULT,
        conversation_states=RESTAURANT_RESERVATION_CONTRACT.allowed_conversation_states,
        user_actions=RESTAURANT_USER_ACTIONS,
    ),
    _detailed_contract(
        category="예약",
        title="미용실 예약",
        default_result=DEFAULT_HAIR_SALON_STRUCTURED_RESULT,
        conversation_states=HAIR_SALON_RESERVATION_CONTRACT.allowed_conversation_states,
        user_actions=HAIR_SALON_USER_ACTIONS,
    ),
    _detailed_contract(
        category="예약",
        title="스터디룸 예약",
        default_result=DEFAULT_STUDY_ROOM_STRUCTURED_RESULT,
        conversation_states=STUDY_ROOM_RESERVATION_CONTRACT.allowed_conversation_states,
        user_actions=STUDY_ROOM_USER_ACTIONS,
    ),
    _detailed_contract(
        category="교수님",
        title="면담 예약",
        default_result=DEFAULT_APPOINTMENT_STRUCTURED_RESULT,
        conversation_states=PROFESSOR_APPOINTMENT_CONTRACT.allowed_conversation_states,
        user_actions=PROFESSOR_APPOINTMENT_USER_ACTIONS,
    ),
    _detailed_contract(
        category="교수님",
        title="과제 문의",
        default_result=DEFAULT_ASSIGNMENT_STRUCTURED_RESULT,
        conversation_states=PROFESSOR_ASSIGNMENT_CONTRACT.allowed_conversation_states,
        user_actions=PROFESSOR_ASSIGNMENT_USER_ACTIONS,
    ),
    _detailed_contract(
        category="교수님",
        title="결석 사유 전달",
        default_result=DEFAULT_ABSENCE_STRUCTURED_RESULT,
        conversation_states=PROFESSOR_ABSENCE_CONTRACT.allowed_conversation_states,
        user_actions=PROFESSOR_ABSENCE_USER_ACTIONS,
    ),
    *(
        _workflow_contract(spec)
        for spec in (
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
    ),
)

if len({contract.scenario_key for contract in _CONTRACTS}) != len(_CONTRACTS):
    raise RuntimeError("structured NLU evaluation scenario keys must be unique")

EVALUATION_CONTRACTS = MappingProxyType(
    {contract.scenario_key: contract for contract in _CONTRACTS}
)
