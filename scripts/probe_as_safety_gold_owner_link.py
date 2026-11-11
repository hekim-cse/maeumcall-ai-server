"""Development-only link decision with a reviewed hazard owner as oracle input.

The existing target and event oracle inputs are unchanged. Only a reviewed
hazard-owner clause and contiguous quote are added; no model call occurs here.
"""

from __future__ import annotations

from scripts.probe_as_safety_clause_index import split_clauses
from scripts.probe_as_safety_oracle_relation import (
    relation_messages,
    relation_schema,
    validate_relation,
)


def gold_owner_link_schema() -> dict:
    """Reuse the frozen finite three-way relation response shape."""
    return relation_schema()


def gold_owner_link_messages(
    user_message: str,
    *,
    product_index: int,
    hazard_index: int,
    event_status: str,
    target_mention: str,
    hazard_event_mention: str,
    owner_clause_index: int,
    owner_mention: str,
) -> list[dict[str, str]]:
    """Add exactly two reviewed owner lines to the prior oracle prompt."""
    messages = relation_messages(
        user_message,
        product_index=product_index,
        hazard_index=hazard_index,
        event_status=event_status,
        target_mention=target_mention,
        hazard_event_mention=hazard_event_mention,
    )
    clauses = split_clauses(user_message)
    if (
        type(owner_clause_index) is not int
        or not 1 <= owner_clause_index <= len(clauses)
        or not isinstance(owner_mention, str)
        or not owner_mention.strip()
        or clauses[owner_clause_index - 1].count(owner_mention) != 1
    ):
        raise ValueError("reviewed owner quote does not uniquely anchor its clause")

    anchor = f"검수된 위험 사건 구절: {hazard_event_mention}\n"
    owner_lines = (
        f"검수된 위험 출처 근거 문장: {owner_clause_index}. "
        f"{clauses[owner_clause_index - 1]}\n"
        f"검수된 위험 출처 구절: {owner_mention}\n"
    )
    prompt = messages[1]["content"]
    if prompt.count(anchor) != 1:
        raise ValueError("owner quote insertion anchor differs")
    messages[1]["content"] = prompt.replace(anchor, anchor + owner_lines, 1)
    return messages


def validate_gold_owner_link(raw: str) -> dict[str, str]:
    """Reuse duplicate-key rejection and the exact prior relation contract."""
    return validate_relation(raw)
