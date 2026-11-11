"""Diagnose why the frozen grounded-link v1 contract keeps or abstains.

The v1 parser remains authoritative. Raw model choices and source quotes are
handled only in memory here. Exact text anchoring cannot establish that the
quoted words semantically prove ownership or identity.
"""

from __future__ import annotations

import json

from scripts.probe_as_safety_clause_index import split_clauses
from scripts.probe_as_safety_grounded_entity_link_v1 import (
    _reject_constant,
    _unique_object,
    validate_grounded_entity_link,
)

ANCHOR_STATUSES = frozenset(
    {
        "model_abstained",
        "accepted",
        "rejected_missing_evidence",
        "rejected_invalid_quote",
        "rejected_missing_target",
        "rejected_missing_owner",
    }
)


def assess_grounded_entity_link(
    raw: str,
    user_message: str,
    *,
    target_mention: str,
    product_index: int,
    owner_mention: str,
    owner_clause_index: int,
) -> dict:
    """Return finite raw/effective links and the first failed anchor stage.

    Invalid JSON or structure raises exactly as v1 does. In a valid response,
    missing/unsupported quote evidence retains v1's unresolved fallback.
    """
    effective = validate_grounded_entity_link(
        raw,
        user_message,
        target_mention=target_mention,
        product_index=product_index,
        owner_mention=owner_mention,
        owner_clause_index=owner_clause_index,
    )
    parsed = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    raw_link = parsed["entity_link"]
    evidence = parsed["evidence"]

    if raw_link == "unresolved":
        anchor_status = "model_abstained"
    elif effective["entity_link"] == raw_link:
        anchor_status = "accepted"
    elif not evidence:
        anchor_status = "rejected_missing_evidence"
    else:
        clauses = split_clauses(user_message)
        invalid_quote = any(
            not 1 <= item["clause_index"] <= len(clauses)
            or not item["quote"].strip()
            or item["quote"] != item["quote"].strip()
            or clauses[item["clause_index"] - 1].count(item["quote"]) != 1
            for item in evidence
        )
        if invalid_quote:
            anchor_status = "rejected_invalid_quote"
        elif not any(
            item["clause_index"] == product_index and target_mention in item["quote"]
            for item in evidence
        ):
            anchor_status = "rejected_missing_target"
        else:
            anchor_status = "rejected_missing_owner"

    return {
        "raw_link": raw_link,
        "anchor_status": anchor_status,
        "effective_link": effective["entity_link"],
        "evidence": effective["evidence"],
    }
