"""Exact source-clause anchoring for the next A/S development experiment."""

from __future__ import annotations

import hashlib
import re

from experiments.as_safety_v2.json_contract import ValidationError


def split_clauses(text: str) -> tuple[str, ...]:
    """Preserve the source text in numbered clauses, as prior A/S data did."""
    if type(text) is not str or not text.strip():
        raise ValidationError("source_text_invalid", "user_message")
    clauses = tuple(part.strip() for part in re.split(r"(?<=[.!?。])\s+", text) if part.strip())
    if not clauses:
        raise ValidationError("source_text_invalid", "user_message")
    return clauses


def anchor_span(item: object, clauses: tuple[str, ...], *, field: str) -> dict | None:
    """Return an exact unique quote with Unicode codepoint offsets in its clause.

    This proves textual provenance only; it does not prove that the model chose
    the correct hazard or owner.
    """
    if item is None:
        return None
    if type(item) is not dict or set(item) != {"clause_index", "quote"}:
        raise ValidationError("quote_fields_invalid", field)
    index, quote = item["clause_index"], item["quote"]
    if type(index) is not int or not 1 <= index <= len(clauses):
        raise ValidationError("quote_index_invalid", field)
    if type(quote) is not str:
        raise ValidationError("quote_type_invalid", field)
    if not quote.strip() or quote != quote.strip():
        raise ValidationError("quote_blank", field)
    start = clauses[index - 1].find(quote)
    if start < 0:
        raise ValidationError("quote_unanchored", field)
    if clauses[index - 1].find(quote, start + 1) >= 0:
        raise ValidationError("quote_nonunique", field)
    return {
        "clause_index": index,
        "quote": quote,
        "start": start,
        "end": start + len(quote),
        "quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
    }
