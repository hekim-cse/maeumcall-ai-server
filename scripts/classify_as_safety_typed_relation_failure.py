"""Classify typed-relation contract failures without persisting model text."""

from __future__ import annotations

import json

from scripts.probe_as_safety_typed_relation import validate_typed_relation

REASONS = (
    "json_syntax",
    "field_set",
    "index_type",
    "enum",
    "empty_event_conflict",
    "missing_target",
    "missing_event_or_occurrence",
    "missing_source",
    "bounded_decision",
    "response_failure",
    "response_incomplete",
    "other_contract",
)

_MESSAGES = {
    "typed relation fields differ": "field_set",
    "source index must be an integer": "index_type",
    "typed relation value outside finite choices": "enum",
    "empty event fields disagree": "empty_event_conflict",
    "service target evidence is required": "missing_target",
    "event and occurrence evidence are required": "missing_event_or_occurrence",
    "source relation lacks evidence": "missing_source",
}


def classify_candidate(raw: str, clause_count: int) -> tuple[dict | None, str | None]:
    """Return a bounded decision or one finite reason, never raw text."""
    try:
        decision = validate_typed_relation(raw, clause_count)
    except json.JSONDecodeError:
        return None, "json_syntax"
    except ValueError as error:
        return None, _MESSAGES.get(str(error), "other_contract")
    return decision, None
