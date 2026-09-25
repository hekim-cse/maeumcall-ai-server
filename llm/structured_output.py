from __future__ import annotations

import json
import logging
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, TypeVar

from core.observability import record_contract_failure, record_structured_output_retry
from llm.errors import AIResponseValidationError

logger = logging.getLogger(__name__)

ValidatedOutput = TypeVar("ValidatedOutput")
Completion = Callable[[list[dict[str, str]]], str]
Validator = Callable[[dict[str, Any]], ValidatedOutput]


@dataclass(frozen=True)
class ActionFieldRule:
    """Declare which current-turn field deltas one action may carry."""

    allowed_fields: frozenset[str] = frozenset()
    required_fields: frozenset[str] = frozenset()
    require_any: bool = False


def build_action_field_contract(
    *,
    field_names: Collection[str],
    user_actions: Collection[str],
    rules: Mapping[str, ActionFieldRule],
) -> Mapping[str, ActionFieldRule]:
    """Freeze a complete action-to-current-turn-field contract."""
    fields = frozenset(field_names)
    actions = frozenset(user_actions)
    if set(rules) != actions:
        missing = sorted(actions - set(rules))
        unknown = sorted(set(rules) - actions)
        raise ValueError(
            f"action-field contract must cover every action; missing={missing}, unknown={unknown}"
        )

    normalized: dict[str, ActionFieldRule] = {}
    for action, rule in rules.items():
        if not rule.allowed_fields <= fields:
            raise ValueError(f"{action} allows fields outside the structured result")
        if not rule.required_fields <= rule.allowed_fields:
            raise ValueError(f"{action} requires fields it does not allow")
        if rule.require_any and not rule.allowed_fields:
            raise ValueError(f"{action} requires a field but allows none")
        normalized[action] = rule
    return MappingProxyType(normalized)


def validate_action_field_delta(
    fields: Mapping[str, str | None],
    *,
    user_action: str,
    contract: Mapping[str, ActionFieldRule],
) -> None:
    """Reject model output whose action contradicts its current-turn field delta."""
    rule = contract.get(user_action)
    if rule is None:
        raise ValueError(f"user_action has no field contract: {user_action}")

    present_fields = {key for key, value in fields.items() if value is not None}
    forbidden = present_fields - rule.allowed_fields
    if forbidden:
        raise ValueError(f"{user_action} must not include current-turn fields: {sorted(forbidden)}")
    missing = rule.required_fields - present_fields
    if missing:
        raise ValueError(f"{user_action} requires current-turn fields: {sorted(missing)}")
    if rule.require_any and not present_fields:
        raise ValueError(f"{user_action} requires at least one current-turn field")


def apply_action_field_delta(
    current_fields: Mapping[str, str | None],
    current_turn_fields: Mapping[str, str | None],
    *,
    user_action: str,
    change_targets: Mapping[str, str] | None = None,
    reset_actions: Collection[str] = (),
) -> dict[str, str | None]:
    """Apply a validated current-turn delta without inferring or rewriting an action."""
    if set(current_fields) != set(current_turn_fields):
        raise ValueError("current and current-turn field keys must match")

    next_fields = dict(current_fields)
    if user_action in reset_actions:
        return {key: None for key in current_fields}

    target = (change_targets or {}).get(user_action)
    if target is not None:
        if target not in next_fields:
            raise ValueError(f"change target is not a structured field: {target}")
        next_fields[target] = current_turn_fields[target]
        return next_fields

    for key, value in current_turn_fields.items():
        if value is not None:
            next_fields[key] = value
    return next_fields


def require_exact_keys(data: Mapping[str, Any], expected: Collection[str]) -> None:
    """Reject missing and unknown model-output keys before domain normalization."""
    expected_keys = set(expected)
    if set(data) != expected_keys:
        raise ValueError(f"response keys must be exactly {sorted(expected_keys)}")


def build_state_action_contract(
    actions_by_state: Mapping[str, Collection[str]],
) -> tuple[Mapping[str, frozenset[str]], frozenset[str]]:
    """Freeze one state-to-action contract and derive its complete action set."""
    if not actions_by_state:
        raise ValueError("state-action contract must not be empty")
    normalized: dict[str, frozenset[str]] = {}
    for state, actions in actions_by_state.items():
        if not state.strip() or not actions or any(not action.strip() for action in actions):
            raise ValueError("state-action contract entries must not be blank")
        normalized[state] = frozenset(actions)
    return MappingProxyType(normalized), frozenset().union(*normalized.values())


def optional_string(data: dict[str, Any], field: str) -> str | None:
    if field not in data:
        raise ValueError(f"{field} is required")
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string or null")
    normalized = value.strip()
    return normalized or None


def allowed_string(data: dict[str, Any], field: str, allowed: set[str]) -> str:
    value = data.get(field)
    if value not in allowed:
        raise ValueError(f"{field} must be one of {sorted(allowed)}")
    return value


def allowed_string_for_state(
    data: dict[str, Any],
    field: str,
    *,
    conversation_state: str,
    allowed_by_state: Mapping[str, frozenset[str]],
) -> str:
    """Read one string whose allowed values are defined by the current state."""
    allowed = allowed_by_state.get(conversation_state)
    if allowed is None:
        raise ValueError(f"unsupported conversation_state: {conversation_state}")
    return allowed_string(data, field, set(allowed))


def allowed_actions_json_for_state(
    conversation_state: str,
    allowed_by_state: Mapping[str, frozenset[str]],
) -> str:
    """Serialize the validator's exact action set for inclusion in a model prompt."""
    allowed = allowed_by_state.get(conversation_state)
    if allowed is None:
        raise ValueError(f"unsupported conversation_state: {conversation_state}")
    return json.dumps(sorted(allowed), ensure_ascii=False)


def action_field_rules_json_for_state(
    conversation_state: str,
    *,
    allowed_by_state: Mapping[str, frozenset[str]],
    contract: Mapping[str, ActionFieldRule],
) -> str:
    """Serialize the validator's exact current-turn field rules for a prompt."""
    allowed_actions = allowed_by_state.get(conversation_state)
    if allowed_actions is None:
        raise ValueError(f"unsupported conversation_state: {conversation_state}")
    missing_rules = allowed_actions - set(contract)
    if missing_rules:
        raise ValueError(f"allowed actions have no field rules: {sorted(missing_rules)}")
    payload = {
        action: {
            "allowed_fields": sorted(contract[action].allowed_fields),
            "required_fields": sorted(contract[action].required_fields),
            "requires_at_least_one_allowed_field": contract[action].require_any,
        }
        for action in sorted(allowed_actions)
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def complete_validated_json(
    messages: list[dict[str, str]],
    *,
    completion: Completion,
    validator: Validator[ValidatedOutput],
    operation: str,
    max_attempts: int = 2,
) -> ValidatedOutput:
    """Generate one strict JSON object and validate its domain contract.

    A validation failure is retried with the validation reason. No inferred values,
    regex extraction, or synthetic success result is produced.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    retry_messages = list(messages)
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        raw = completion(retry_messages)

        try:
            if not raw or not raw.strip():
                raise ValueError("response must not be empty")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("response must be a JSON object")
            return validator(parsed)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            last_error = exc
            failure_reason = type(exc).__name__
            record_contract_failure("structured_output", failure_reason)
            logger.warning(
                "Structured response validation failed (attempt %d/%d): %s",
                attempt,
                max_attempts,
                type(exc).__name__,
            )
            if attempt < max_attempts:
                record_structured_output_retry(operation, failure_reason)
                retry_messages.extend(
                    [
                        {"role": "assistant", "content": raw},
                        {
                            "role": "user",
                            "content": (
                                "이전 출력은 JSON 계약 검증에 실패했습니다. "
                                f"검증 오류: {exc}. 원래 스키마를 지킨 JSON 객체 하나만 다시 출력하세요."
                            ),
                        },
                    ]
                )
    record_contract_failure("structured_output", "RETRIES_EXHAUSTED")
    raise AIResponseValidationError("Structured response failed validation") from last_error
