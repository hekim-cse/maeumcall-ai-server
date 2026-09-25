from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from llm.structured_output import (
    ActionFieldRule,
    build_action_field_contract,
    validate_action_field_delta,
)
from services.flow.service_workflow.contracts import ServiceWorkflowSpec


@dataclass(frozen=True)
class ServiceWorkflowTurnContract:
    field_names: frozenset[str]
    provide_action: str
    change_action: str
    control_actions: frozenset[str]
    action_field_contract: Mapping[str, ActionFieldRule]

    @property
    def canonical_payload(self) -> str:
        payload = {
            "kind": "service_workflow_turn_delta_v3",
            "provide_action": self.provide_action,
            "change_action": self.change_action,
            "change_field_must_name_only_present_field": True,
            "empty_change_clears_target": True,
            "provide_fields_must_be_missing_from_current_context": True,
            "change_target_must_exist_in_current_context": True,
            "control_actions": sorted(self.control_actions),
            "action_field_rules": {
                action: {
                    "allowed_fields": sorted(rule.allowed_fields),
                    "required_fields": sorted(rule.required_fields),
                    "require_any": rule.require_any,
                }
                for action, rule in sorted(self.action_field_contract.items())
            },
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def validate(
        self,
        *,
        fields: dict[str, str | None],
        current_fields: dict[str, str | None],
        user_action: str,
        change_field: str | None,
    ) -> None:
        if set(current_fields) != self.field_names:
            raise ValueError("current_fields must match the workflow field contract")
        validate_action_field_delta(
            fields,
            user_action=user_action,
            contract=self.action_field_contract,
        )
        present_fields = {key for key, value in fields.items() if value is not None}
        if user_action == self.provide_action:
            already_collected = {
                field_name
                for field_name in present_fields
                if current_fields[field_name] is not None
            }
            if already_collected:
                raise ValueError(
                    "provide_details may include only fields missing from current_fields: "
                    f"{sorted(already_collected)}"
                )
        if user_action == self.change_action:
            if change_field not in self.field_names:
                raise ValueError("change_field must name a workflow field")
            if current_fields[change_field] is None:
                raise ValueError("change_detail must target a previously collected field")
            if present_fields - {change_field}:
                raise ValueError("change_detail may include only the field named by change_field")
            replacement = fields[change_field]
            if replacement is not None and replacement == current_fields[change_field]:
                raise ValueError("change_detail must replace the current field with a new value")
        elif change_field is not None:
            raise ValueError("change_field must be null unless user_action is change_detail")


def build_service_workflow_turn_contract(
    spec: ServiceWorkflowSpec,
) -> ServiceWorkflowTurnContract:
    field_names = frozenset(spec.field_keys)
    provide_action = "provide_details"
    change_action = "change_detail"
    rules = {action: ActionFieldRule() for action in spec.user_actions} | {
        provide_action: ActionFieldRule(allowed_fields=field_names, require_any=True),
        change_action: ActionFieldRule(allowed_fields=field_names),
    }
    action_field_contract = build_action_field_contract(
        field_names=field_names,
        user_actions=spec.user_actions,
        rules=rules,
    )
    return ServiceWorkflowTurnContract(
        field_names=field_names,
        provide_action=provide_action,
        change_action=change_action,
        control_actions=spec.user_actions - {provide_action, change_action},
        action_field_contract=action_field_contract,
    )


def validate_service_workflow_turn_delta(
    spec: ServiceWorkflowSpec,
    *,
    fields: dict[str, str | None],
    current_fields: dict[str, str | None],
    user_action: str,
    change_field: str | None,
) -> None:
    """Validate one workflow action against values extracted from the same utterance."""
    build_service_workflow_turn_contract(spec).validate(
        fields=fields,
        current_fields=current_fields,
        user_action=user_action,
        change_field=change_field,
    )
