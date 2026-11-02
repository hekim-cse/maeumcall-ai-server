"""Experimental GGUF JSON schema for service-workflow action/field combinations.

This constrains output shape only. Live server validation remains authoritative,
and the schema cannot determine whether a field value was stated by the user.
"""

from __future__ import annotations

from services.flow.service_workflow.contracts import MAX_WORKFLOW_FIELD_LENGTH, ServiceWorkflowSpec


def workflow_response_schema(
    spec: ServiceWorkflowSpec,
    *,
    conversation_state: str,
    current_fields: dict[str, str | None],
) -> dict:
    if set(current_fields) != set(spec.field_keys):
        raise ValueError("current_fields must match workflow field keys")
    if conversation_state not in spec.actions_by_state:
        raise ValueError("unknown workflow state")

    properties = {}
    for field in spec.fields:
        if field.options:
            properties[field.key] = {"enum": [None, *(option.value for option in field.options)]}
        else:
            properties[field.key] = {
                "type": ["string", "null"],
                "minLength": 1,
                "maxLength": MAX_WORKFLOW_FIELD_LENGTH,
            }

    def branch(action: str, present_field: str | None = None, change_field: str | None = None):
        field_properties = {}
        for name, shape in properties.items():
            if action == "provide_details" and current_fields[name] is not None:
                field_properties[name] = {"type": "null"}
            elif action == "provide_details" and name == present_field:
                if "enum" in shape:
                    field_properties[name] = {
                        "enum": [value for value in shape["enum"] if value is not None]
                    }
                else:
                    field_properties[name] = {**shape, "type": "string"}
            elif action == "provide_details":
                field_properties[name] = shape
            elif action == "change_detail" and name == change_field:
                field_properties[name] = shape
            else:
                field_properties[name] = {"type": "null"}
        return {
            "type": "object",
            "properties": {
                "intent": {"enum": [spec.intent]},
                "fields": {
                    "type": "object",
                    "properties": field_properties,
                    "required": list(spec.field_keys),
                    "additionalProperties": False,
                },
                "user_action": {"enum": [action]},
                "change_field": (
                    {"enum": [change_field]} if action == "change_detail" else {"type": "null"}
                ),
            },
            "required": ["intent", "fields", "user_action", "change_field"],
            "additionalProperties": False,
        }

    branches = []
    for action in sorted(spec.actions_by_state[conversation_state]):
        if action == "provide_details":
            branches.extend(
                branch(action, present_field=name)
                for name in spec.field_keys
                if current_fields[name] is None
            )
        elif action == "change_detail":
            branches.extend(
                branch(action, change_field=name)
                for name in spec.field_keys
                if current_fields[name] is not None
            )
        else:
            branches.append(branch(action))
    if not branches:
        raise ValueError("state has no valid schema branches")
    return {"anyOf": branches}
