"""Strict model JSON parsing with bounded, field-addressable failure codes."""

from __future__ import annotations

import json


class ValidationError(ValueError):
    """A contract failure without raw model output or arbitrary error text."""

    def __init__(self, code: str, field: str) -> None:
        if not code or not field:
            raise ValueError("validation code and field must be nonempty")
        self.code = code
        self.field = field
        super().__init__(f"{code}: {field}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("duplicate_key", "$")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise ValidationError("nonfinite_number", "$")


def parse_model_json(raw: str) -> object:
    """Parse JSON and reject duplicate keys and nonfinite numbers at every depth."""
    if type(raw) is not str:
        raise ValidationError("response_type_invalid", "$")
    try:
        return json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as error:
        raise ValidationError("invalid_json", "$") from error
