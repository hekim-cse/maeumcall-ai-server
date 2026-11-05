"""Check model-supplied source spans without treating them as semantic proof."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def validate_source_evidence(
    utterance: str,
    fields: Mapping[str, str | None],
    evidence: Any,
) -> None:
    """Require one exact utterance span for each non-null current-turn field.

    This proves only that a quote was copied from the utterance. It cannot prove
    that a normalized value follows from the quote or that the field is needed.
    Errors contain field names and fixed codes, never user text or field values.
    """
    if not isinstance(evidence, dict):
        raise ValueError("evidence_not_object")
    expected = {name for name, value in fields.items() if value is not None}
    if set(evidence) != expected:
        raise ValueError("evidence_field_set_mismatch")

    for name, span in evidence.items():
        if not isinstance(span, dict) or set(span) != {"start", "end", "quote"}:
            raise ValueError(f"evidence_shape_invalid:{name}")
        start, end, quote = span["start"], span["end"], span["quote"]
        if type(start) is not int or type(end) is not int or not isinstance(quote, str):
            raise ValueError(f"evidence_type_invalid:{name}")
        if not (0 <= start < end <= len(utterance)):
            raise ValueError(f"evidence_range_invalid:{name}")
        if not quote.strip() or utterance[start:end] != quote:
            raise ValueError(f"evidence_quote_mismatch:{name}")
