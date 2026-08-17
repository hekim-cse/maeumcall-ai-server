from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional, Tuple

from services.flow.common.state_contract import (
    DetailedGraphContract,
    ScenarioStateContractError,
)


WORKFLOW_ACTIONS = frozenset(
    {
        "provide_details",
        "confirm_details",
        "change_detail",
        "cancel_workflow",
        "go_closing",
        "end_call",
        "unknown",
    }
)
WORKFLOW_STATUSES = frozenset({"in_progress", "ready", "cancelled", "blocked"})
MAX_WORKFLOW_FIELD_LENGTH = 1_000


@dataclass(frozen=True)
class FieldOption:
    value: str
    label: str

    def __post_init__(self) -> None:
        if not self.value or not self.label:
            raise ValueError("workflow field option must not be empty")


@dataclass(frozen=True)
class FieldContract:
    key: str
    label: str
    description: str
    question: str
    replies: Tuple[str, ...]
    options: Tuple[FieldOption, ...] = ()

    def __post_init__(self) -> None:
        if not self.key or not self.label or not self.description or not self.question:
            raise ValueError("workflow field metadata must not be empty")
        if not self.replies or any(not reply.strip() for reply in self.replies):
            raise ValueError(f"workflow field replies must not be empty: {self.key}")
        option_values = tuple(option.value for option in self.options)
        if len(option_values) != len(set(option_values)):
            raise ValueError(f"workflow field options must be unique: {self.key}")

    def display_value(self, value: Optional[str]) -> Optional[str]:
        for option in self.options:
            if option.value == value:
                return option.label
        return value


@dataclass(frozen=True)
class GuardContract:
    field_key: str
    value: str
    state: str
    message: str
    replies: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.field_key or not self.value or not self.state or not self.message:
            raise ValueError("workflow guard metadata must not be empty")
        if not self.replies or any(not reply.strip() for reply in self.replies):
            raise ValueError(f"workflow guard replies must not be empty: {self.state}")


@dataclass(frozen=True)
class ServiceWorkflowSpec:
    category: str
    title: str
    graph_name: str
    intent: str
    collecting_state: str
    confirming_state: str
    ready_state: str
    fields: Tuple[FieldContract, ...]
    confirmation_prefix: str
    ready_message: str
    cancelled_message: str
    closing_message: str
    ready_replies: Tuple[str, ...]
    branch_field: Optional[str] = None
    ready_messages_by_branch: Tuple[Tuple[str, str], ...] = ()
    guards: Tuple[GuardContract, ...] = ()

    def __post_init__(self) -> None:
        field_keys = self.field_keys
        if not self.category or not self.title or not self.graph_name or not self.intent:
            raise ValueError("workflow identity metadata must not be empty")
        if not self.fields or len(field_keys) != len(set(field_keys)):
            raise ValueError(f"workflow fields must be non-empty and unique: {self.graph_name}")
        states = {self.collecting_state, self.confirming_state, self.ready_state}
        if len(states) != 3 or "END" in states:
            raise ValueError(f"workflow state names must be unique: {self.graph_name}")
        if not all(
            (
                self.confirmation_prefix,
                self.ready_message,
                self.cancelled_message,
                self.closing_message,
            )
        ):
            raise ValueError(f"workflow response messages must not be empty: {self.graph_name}")
        if not self.ready_replies or any(not reply.strip() for reply in self.ready_replies):
            raise ValueError(f"workflow ready replies must not be empty: {self.graph_name}")
        branch_messages = dict(self.ready_messages_by_branch)
        if len(branch_messages) != len(self.ready_messages_by_branch):
            raise ValueError(f"workflow branch values must be unique: {self.graph_name}")
        if any(not value or not message for value, message in self.ready_messages_by_branch):
            raise ValueError(f"workflow branch messages must not be empty: {self.graph_name}")
        if self.branch_field is None and branch_messages:
            raise ValueError(f"workflow branch field is required: {self.graph_name}")
        if self.branch_field is not None:
            branch_contract = next(
                (field for field in self.fields if field.key == self.branch_field),
                None,
            )
            if branch_contract is None or not branch_contract.options:
                raise ValueError(f"workflow branch field must have options: {self.graph_name}")
            allowed_branches = {option.value for option in branch_contract.options}
            if not set(branch_messages).issubset(allowed_branches):
                raise ValueError(f"workflow branch message is not declared: {self.graph_name}")
        guard_states = set()
        for guard in self.guards:
            field = next((item for item in self.fields if item.key == guard.field_key), None)
            if field is None or guard.value not in {option.value for option in field.options}:
                raise ValueError(f"workflow guard value is not declared: {self.graph_name}")
            if guard.state in guard_states or guard.state in states or guard.state in {"greeting", "closing", "cancelled", "END"}:
                raise ValueError(f"workflow guard state must be unique: {self.graph_name}")
            guard_states.add(guard.state)

    @property
    def field_keys(self) -> Tuple[str, ...]:
        return tuple(field.key for field in self.fields)

    @property
    def allowed_conversation_states(self) -> FrozenSet[str]:
        return frozenset(
            {
                "greeting",
                self.collecting_state,
                self.confirming_state,
                self.ready_state,
                "cancelled",
                "closing",
                "END",
                *(guard.state for guard in self.guards),
            }
        )

    def ready_message_for(self, fields: Dict[str, Optional[str]]) -> str:
        branch_value = fields.get(self.branch_field) if self.branch_field else None
        return dict(self.ready_messages_by_branch).get(branch_value, self.ready_message)

    def matching_guard(self, fields: Dict[str, Optional[str]]) -> Optional[GuardContract]:
        return next(
            (
                guard
                for guard in self.guards
                if fields.get(guard.field_key) == guard.value
            ),
            None,
        )

    def guard_for_state(self, state: str) -> Optional[GuardContract]:
        return next((guard for guard in self.guards if guard.state == state), None)


def compact_service_workflow_state(spec: ServiceWorkflowSpec, result: Dict[str, Any]) -> Dict[str, Any]:
    raw_fields = result.get("fields") or {}
    return {
        "intent": result.get("intent") or spec.intent,
        "fields": {key: raw_fields.get(key) for key in spec.field_keys},
        "conversation_state": result.get("conversation_state"),
        "missing_fields": result.get("missing_fields") or [],
        "last_ai_message": result.get("ai_message"),
        "user_action": result.get("user_action") or "unknown",
        "change_field": result.get("change_field"),
        "workflow_status": result.get("workflow_status") or "in_progress",
    }


def validate_service_workflow_state(spec: ServiceWorkflowSpec, state: Dict[str, Any]) -> None:
    if not state:
        return

    intent = state.get("intent")
    if intent != spec.intent:
        _invalid_state()

    raw_fields = state.get("fields")
    if not isinstance(raw_fields, dict) or set(raw_fields) != set(spec.field_keys):
        _invalid_state()
    for value in raw_fields.values():
        if value is not None and (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > MAX_WORKFLOW_FIELD_LENGTH
        ):
            _invalid_state()

    missing_fields = state.get("missing_fields")
    if not isinstance(missing_fields, list) or len(missing_fields) != len(set(missing_fields)):
        _invalid_state()
    if any(field not in spec.field_keys for field in missing_fields):
        _invalid_state()

    user_action = state.get("user_action")
    if user_action not in WORKFLOW_ACTIONS:
        _invalid_state()
    change_field = state.get("change_field")
    if change_field is not None and change_field not in spec.field_keys:
        _invalid_state()
    workflow_status = state.get("workflow_status")
    if workflow_status not in WORKFLOW_STATUSES:
        _invalid_state()
    last_ai_message = state.get("last_ai_message")
    if last_ai_message is not None and (
        not isinstance(last_ai_message, str) or len(last_ai_message) > 4_000
    ):
        _invalid_state()
    if (user_action == "change_detail") != (change_field is not None):
        _invalid_state()

    actual_missing = [key for key in spec.field_keys if not raw_fields[key]]
    if missing_fields != actual_missing:
        _invalid_state()
    conversation_state = state.get("conversation_state")
    if conversation_state not in {"closing", "END"}:
        expected_statuses = {
            spec.ready_state: "ready",
            "cancelled": "cancelled",
            **{guard.state: "blocked" for guard in spec.guards},
        }
        expected_status = expected_statuses.get(conversation_state, "in_progress")
        if workflow_status != expected_status:
            _invalid_state()
    if conversation_state in {spec.confirming_state, spec.ready_state} and actual_missing:
        _invalid_state()


def _invalid_state() -> None:
    raise ScenarioStateContractError(
        "SCENARIO_STATE_INVALID",
        "대화 상태의 업무 필드 계약이 올바르지 않습니다.",
    )


def build_service_workflow_contract(spec: ServiceWorkflowSpec) -> DetailedGraphContract:
    from services.flow.service_workflow.graph import build_service_workflow_graph

    return DetailedGraphContract(
        category=spec.category,
        title=spec.title,
        graph=build_service_workflow_graph(spec),
        compact_state=lambda result: compact_service_workflow_state(spec, result),
        defaults={
            "intent": spec.intent,
            "fields": {key: None for key in spec.field_keys},
            "workflow_status": "in_progress",
        },
        allowed_conversation_states=spec.allowed_conversation_states,
        validate_state=lambda state: validate_service_workflow_state(spec, state),
    )
