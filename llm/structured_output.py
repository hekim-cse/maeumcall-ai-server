from __future__ import annotations

import json
import logging
from collections.abc import Callable, Collection, Mapping
from types import MappingProxyType
from typing import Any, TypeVar

from core.observability import record_contract_failure, record_structured_output_retry
from llm.errors import AIResponseValidationError

logger = logging.getLogger(__name__)

ValidatedOutput = TypeVar("ValidatedOutput")
Completion = Callable[[list[dict[str, str]]], str]
Validator = Callable[[dict[str, Any]], ValidatedOutput]


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
