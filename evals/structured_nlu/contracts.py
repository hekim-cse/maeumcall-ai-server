from __future__ import annotations

from collections.abc import Mapping
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
    PROFESSOR_ABSENCE_ACTIONS_BY_STATE,
    PROFESSOR_ABSENCE_USER_ACTIONS,
)
from services.flow.professor.appointment.llm_structured import (
    DEFAULT_APPOINTMENT_STRUCTURED_RESULT,
    PROFESSOR_APPOINTMENT_ACTIONS_BY_STATE,
    PROFESSOR_APPOINTMENT_USER_ACTIONS,
)
from services.flow.professor.assignment.llm_structured import (
    DEFAULT_ASSIGNMENT_STRUCTURED_RESULT,
    PROFESSOR_ASSIGNMENT_ACTIONS_BY_STATE,
    PROFESSOR_ASSIGNMENT_USER_ACTIONS,
)
from services.flow.reservation.hair_salon.llm_structured import (
    DEFAULT_HAIR_SALON_STRUCTURED_RESULT,
    HAIR_SALON_ACTIONS_BY_STATE,
    HAIR_SALON_USER_ACTIONS,
)
from services.flow.reservation.hospital.llm_structured import (
    DEFAULT_HOSPITAL_STRUCTURED_RESULT,
    HOSPITAL_ACTIONS_BY_STATE,
    HOSPITAL_USER_ACTIONS,
)
from services.flow.reservation.restaurant.llm_structured import (
    DEFAULT_RESTAURANT_STRUCTURED_RESULT,
    RESTAURANT_ACTIONS_BY_STATE,
    RESTAURANT_USER_ACTIONS,
)
from services.flow.reservation.study_room.llm_structured import (
    DEFAULT_STUDY_ROOM_STRUCTURED_RESULT,
    STUDY_ROOM_ACTIONS_BY_STATE,
    STUDY_ROOM_USER_ACTIONS,
)
from services.flow.service_workflow.contracts import (
    ServiceWorkflowSpec,
    validate_service_workflow_context,
)
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
    actions_by_state: tuple[tuple[str, frozenset[str]], ...]
    field_options: tuple[tuple[str, frozenset[str]], ...] = ()
    workflow_spec: ServiceWorkflowSpec | None = None

    def allowed_actions_for_state(self, conversation_state: str) -> frozenset[str]:
        actions = dict(self.actions_by_state).get(conversation_state)
        if actions is None:
            raise ValueError(
                f"conversation_state is not evaluated for {self.scenario_key}: {conversation_state}"
            )
        return actions

    def validate_prediction(
        self,
        *,
        intent: str | None,
        fields: dict[str, str | None],
        user_action: str,
        change_field: str | None,
        conversation_state: str,
    ) -> None:
        """Validate normalized model output against the live scenario contract."""
        if set(fields) != set(self.field_names):
            raise ValueError(
                f"prediction fields do not match {self.scenario_key}: {sorted(fields)}"
            )
        if intent not in self.allowed_intents:
            raise ValueError(f"prediction intent is not allowed for {self.scenario_key}: {intent}")
        if user_action not in self.allowed_actions_for_state(conversation_state):
            raise ValueError(
                f"prediction user_action is not allowed for {self.scenario_key} "
                f"in {conversation_state}: {user_action}"
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

    def validate_current_fields(
        self,
        *,
        conversation_state: str,
        current_fields: dict[str, str | None],
    ) -> None:
        if self.workflow_spec is None:
            if current_fields:
                raise ValueError("current_fields must be empty for this extractor")
            return
        validate_service_workflow_context(
            self.workflow_spec,
            conversation_state=conversation_state,
            fields=current_fields,
        )


def _detailed_contract(
    *,
    category: str,
    title: str,
    default_result: dict[str, object],
    actions_by_state: Mapping[str, frozenset[str]],
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
    declared_actions = frozenset().union(*actions_by_state.values())
    if declared_actions != user_actions:
        raise RuntimeError(f"state action contract is incomplete: {category}:{title}")
    return EvaluationContract(
        scenario_key=build_scenario_key(category, title),
        allowed_intents=resolved_intents,
        field_names=field_names,
        conversation_states=frozenset(actions_by_state),
        user_actions=user_actions,
        uses_current_fields=False,
        actions_by_state=tuple(actions_by_state.items()),
    )


def _workflow_contract(spec: ServiceWorkflowSpec) -> EvaluationContract:
    actions_by_state = spec.actions_by_state
    declared_actions = frozenset().union(*actions_by_state.values())
    if declared_actions != spec.user_actions:
        raise RuntimeError(f"workflow state action contract is incomplete: {spec.graph_name}")
    return EvaluationContract(
        scenario_key=build_scenario_key(spec.category, spec.title),
        allowed_intents=frozenset({spec.intent}),
        field_names=spec.field_keys,
        conversation_states=frozenset(actions_by_state),
        user_actions=spec.user_actions,
        uses_current_fields=True,
        actions_by_state=tuple(actions_by_state.items()),
        field_options=tuple(
            (field.key, frozenset(option.value for option in field.options))
            for field in spec.fields
            if field.options
        ),
        workflow_spec=spec,
    )


_CONTRACTS = (
    _detailed_contract(
        category="예약",
        title="병원 예약",
        default_result=DEFAULT_HOSPITAL_STRUCTURED_RESULT,
        actions_by_state=HOSPITAL_ACTIONS_BY_STATE,
        user_actions=HOSPITAL_USER_ACTIONS,
        allowed_intents=frozenset({"reservation", None}),
    ),
    _detailed_contract(
        category="예약",
        title="식당 예약",
        default_result=DEFAULT_RESTAURANT_STRUCTURED_RESULT,
        actions_by_state=RESTAURANT_ACTIONS_BY_STATE,
        user_actions=RESTAURANT_USER_ACTIONS,
    ),
    _detailed_contract(
        category="예약",
        title="미용실 예약",
        default_result=DEFAULT_HAIR_SALON_STRUCTURED_RESULT,
        actions_by_state=HAIR_SALON_ACTIONS_BY_STATE,
        user_actions=HAIR_SALON_USER_ACTIONS,
    ),
    _detailed_contract(
        category="예약",
        title="스터디룸 예약",
        default_result=DEFAULT_STUDY_ROOM_STRUCTURED_RESULT,
        actions_by_state=STUDY_ROOM_ACTIONS_BY_STATE,
        user_actions=STUDY_ROOM_USER_ACTIONS,
    ),
    _detailed_contract(
        category="교수님",
        title="면담 예약",
        default_result=DEFAULT_APPOINTMENT_STRUCTURED_RESULT,
        actions_by_state=PROFESSOR_APPOINTMENT_ACTIONS_BY_STATE,
        user_actions=PROFESSOR_APPOINTMENT_USER_ACTIONS,
    ),
    _detailed_contract(
        category="교수님",
        title="과제 문의",
        default_result=DEFAULT_ASSIGNMENT_STRUCTURED_RESULT,
        actions_by_state=PROFESSOR_ASSIGNMENT_ACTIONS_BY_STATE,
        user_actions=PROFESSOR_ASSIGNMENT_USER_ACTIONS,
    ),
    _detailed_contract(
        category="교수님",
        title="결석 사유 전달",
        default_result=DEFAULT_ABSENCE_STRUCTURED_RESULT,
        actions_by_state=PROFESSOR_ABSENCE_ACTIONS_BY_STATE,
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
