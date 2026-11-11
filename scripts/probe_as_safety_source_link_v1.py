"""Conservative, development-only links between an A/S target and hazard owner.

The caller supplies source-anchored target and owner spans. This module never
extracts those spans, calls a model, or alters the live service graph. It only
uses explicit textual identity, possession, or distinctness; other cases
abstain so an unresolved relation can receive a confirmation step.
"""

from __future__ import annotations

import re

from scripts.probe_as_safety_clause_index import split_clauses

RELATIONS = frozenset({"current", "other", "unknown"})
EVIDENCE_KINDS = frozenset(
    {"same_anchored_entity", "target_possesses_owner", "explicit_other", "unresolved"}
)

_WORD = re.compile(r"[\w가-힣]+", re.UNICODE)
_THIRD_PARTY = re.compile(
    r"^(?P<actor>친구|지인|동료|가족|부모님|형제|이웃|타인|제3자|다른\s*사람)"
    r"(?:의\s*\S+|(?:가|이|께서)\s*(?:쓰는|사용하는|소유한)\s+\S+)"
)
_DEICTIC_HEADS = frozenset({"제품", "기기", "물건", "본체", "이것", "그것", "해당"})


def _target_head(mention: str) -> str | None:
    """Use the last explicit noun token as a narrow textual anchor."""
    tokens = _WORD.findall(mention)
    head = tokens[-1] if tokens else None
    return head if head and len(head) >= 2 and head not in _DEICTIC_HEADS else None


def _anchored(clauses: tuple[str, ...], index: int, mention: str) -> int:
    """Return the only source offset or reject an ambiguous annotation."""
    if (
        type(index) is not int
        or not 1 <= index <= len(clauses)
        or not isinstance(mention, str)
        or not mention.strip()
        or clauses[index - 1].count(mention) != 1
    ):
        raise ValueError("mention must uniquely anchor its numbered source clause")
    return clauses[index - 1].index(mention)


def _explicit_other_noun(owner: str, target_head: str | None) -> bool:
    """Require an identity noun after 'another', never a side or location."""
    nouns = ["제품", "기기", "물건"]
    if target_head is not None:
        nouns.append(target_head)
    noun_pattern = "|".join(re.escape(noun) for noun in nouns)
    return bool(
        re.match(rf"^(?:다른|별도의?)\s*(?:{noun_pattern})(?:$|[의은는이가을를에서\s])", owner)
    )


def link_source(
    utterance: str,
    *,
    target_mention: str,
    target_clause_index: int,
    owner_mention: str | None,
    owner_clause_index: int | None,
) -> dict[str, str]:
    """Classify only explicit links; preserve uncertainty for the rest.

    Identical nouns in different clauses are not enough to identify one
    physical item. A component is linked only by an explicit ``target의``
    possessive prefix. A distinct source needs a lexical other/third-party
    marker, not merely a different surface string.
    """
    if not isinstance(utterance, str):
        raise ValueError("utterance must be text")
    clauses = split_clauses(utterance)
    target_start = _anchored(clauses, target_clause_index, target_mention)
    if owner_mention is None and owner_clause_index is None:
        return {"source_relation": "unknown", "evidence_kind": "unresolved"}
    if owner_mention is None or owner_clause_index is None:
        raise ValueError("owner mention and clause index must both be present")
    owner_start = _anchored(clauses, owner_clause_index, owner_mention)
    head = _target_head(target_mention)

    if (
        target_clause_index == owner_clause_index
        and target_start <= owner_start
        and owner_start + len(owner_mention) <= target_start + len(target_mention)
        and (owner_mention == target_mention or (head is not None and owner_mention == head))
    ):
        return {"source_relation": "current", "evidence_kind": "same_anchored_entity"}
    if target_clause_index != owner_clause_index and owner_mention in target_mention:
        return {"source_relation": "unknown", "evidence_kind": "unresolved"}
    owner_actor = _THIRD_PARTY.match(owner_mention)
    target_actor = _THIRD_PARTY.match(target_mention)
    if owner_actor and target_actor and owner_actor.group("actor") == target_actor.group("actor"):
        return {"source_relation": "unknown", "evidence_kind": "unresolved"}
    if _explicit_other_noun(owner_mention, head) or owner_actor:
        return {"source_relation": "other", "evidence_kind": "explicit_other"}
    if (
        head is not None
        and target_clause_index == owner_clause_index
        and owner_mention.startswith(f"{head}의")
        and owner_start == target_start + target_mention.rfind(head)
    ):
        return {"source_relation": "current", "evidence_kind": "target_possesses_owner"}
    return {"source_relation": "unknown", "evidence_kind": "unresolved"}
