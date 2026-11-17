"""Narrow relation baseline with reviewed A/E/B spans as oracle inputs.

The quote checks establish textual provenance, not that E belongs to B or
that the reviewed spans would be found by the service. Do not use this module
as a production safety gate or interpret its ES score as generalization.
"""

from __future__ import annotations

import re

from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.quotes import anchor_span, split_clauses

OCCURRENCES = frozenset({"observed", "uncertain", "nonoccurring"})
RELATIONS = frozenset({"current", "other", "unknown"})
BASES = frozenset(
    {
        "nonoccurring",
        "owner_missing",
        "conflicting_context",
        "exact_target",
        "target_prefix_candidate",
        "explicit_other_device",
        "insufficient_evidence",
    }
)

_CONTRAST_IN_OWNER = re.compile(r"(?:^|\s)(?:다른|별도|별개|옆|근처|함께|전용)(?:\s|$)")
_CONTRAST_BEFORE_OWNER = re.compile(r"(?:다른|별도|별개)\s*$")


def predict_relation(
    user_message: str,
    *,
    target: dict,
    event_span: dict,
    hazard_owner_span: dict | None,
    occurrence: str,
) -> dict[str, str | None]:
    """Infer only direct lexical relationships, abstaining on all other cases.

    Neither the reviewed relation, expected route, nor evidence-type labels are
    accepted. The event quote is checked but E→B attribution stays an oracle.
    """
    if type(occurrence) is not str or occurrence not in OCCURRENCES:
        raise ValidationError("occurrence_invalid", "occurrence")
    clauses = split_clauses(user_message)
    anchored_target = anchor_span(target, clauses, field="target")
    anchored_event = anchor_span(event_span, clauses, field="event_span")
    if anchored_target is None or anchored_event is None:
        raise ValidationError("required_span_missing", "target_or_event")
    anchored_owner = anchor_span(hazard_owner_span, clauses, field="hazard_owner_span")

    if occurrence == "nonoccurring":
        if anchored_owner is not None:
            raise ValidationError("nonoccurring_owner_invalid", "hazard_owner_span")
        return {"relation": None, "basis": "nonoccurring"}
    if anchored_owner is None:
        return {"relation": "unknown", "basis": "owner_missing"}

    owner = anchored_owner["quote"]
    target_name = anchored_target["quote"]
    before_owner = clauses[anchored_owner["clause_index"] - 1][: anchored_owner["start"]]
    if _CONTRAST_IN_OWNER.search(owner) or _CONTRAST_BEFORE_OWNER.search(before_owner):
        # The one explicit distinct marker is handled below. A phrase such as
        # "다른 [A]" remains unresolved, even if B also contains A's name.
        if (owner == "다른 기기" or owner.startswith("다른 기기의 ")) and target_name not in owner:
            return {"relation": "other", "basis": "explicit_other_device"}
        return {"relation": "unknown", "basis": "conflicting_context"}
    if owner == target_name:
        return {"relation": "current", "basis": "exact_target"}

    for prefix in (f"{target_name} ", f"{target_name}의 "):
        if owner.startswith(prefix):
            suffix = owner[len(prefix) :]
            if suffix and not suffix.startswith("용"):
                # This is only a string-level candidate, never proof that the
                # remainder names a physical part of A.
                return {"relation": "current", "basis": "target_prefix_candidate"}
    return {"relation": "unknown", "basis": "insufficient_evidence"}
