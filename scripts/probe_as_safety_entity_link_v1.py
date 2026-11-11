"""Development-only, single-decision link between two reviewed source mentions.

The full utterance is retained for context. Reviewed mention spans and clause
IDs are oracle inputs; occurrence status, event span, and relation gold are not.
This candidate makes no model call and is not connected to the service graph.
"""

from __future__ import annotations

import json

from scripts.probe_as_safety_clause_index import split_clauses

LINKS = frozenset({"same_or_part", "distinct_item", "unresolved"})

_SYSTEM = "두 원문 구절이 가리키는 물리적 개체의 관계 하나만 JSON으로 판단합니다."
_INSTRUCTION = (
    "구절 A와 B가 같은 물건이거나 B가 A에 소속된 부품·부위임이 문맥상 명확하면 "
    "same_or_part, 별개의 물건임이 명확하면 distinct_item, 어느 쪽인지 확정할 수 "
    "없으면 unresolved를 고르세요. 이름이나 모델명이 같아도 다른 사람이 쓰는 물건이면 "
    "별개입니다. 단순히 가까이 있다는 위치 정보만으로 소속 관계를 확정하지 마세요. "
    "원문과 두 검수 구절만 근거로 판단하고, 다른 정보를 추측하지 마세요. "
    'JSON 객체 하나만 반환하세요: {"entity_link":"same_or_part|distinct_item|unresolved"}.'
)


def entity_link_schema() -> dict:
    """Constrain the response to one finite, text-free decision."""
    return {
        "type": "object",
        "properties": {"entity_link": {"enum": sorted(LINKS)}},
        "required": ["entity_link"],
        "additionalProperties": False,
    }


def _source_clause(clauses: tuple[str, ...], index: int, mention: str) -> str:
    """Reject missing, blank, or nonunique oracle quotes before a model call."""
    if (
        type(index) is not int
        or not 1 <= index <= len(clauses)
        or not isinstance(mention, str)
        or not mention.strip()
        or clauses[index - 1].count(mention) != 1
    ):
        raise ValueError("reviewed mention must uniquely anchor its clause")
    return clauses[index - 1]


def entity_link_messages(
    user_message: str,
    *,
    target_mention: str,
    product_index: int,
    owner_mention: str,
    owner_clause_index: int,
) -> list[dict[str, str]]:
    """Supply only the full utterance and two reviewed mention anchors."""
    if not isinstance(user_message, str) or not user_message.strip():
        raise ValueError("utterance must be nonblank text")
    clauses = split_clauses(user_message)
    target_clause = _source_clause(clauses, product_index, target_mention)
    owner_clause = _source_clause(clauses, owner_clause_index, owner_mention)
    numbered = "\n".join(f"{index}. {clause}" for index, clause in enumerate(clauses, 1))
    return [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": (
                f"원문 전체: {user_message}\n"
                f"번호 문장:\n{numbered}\n"
                f"구절 A 근거: {product_index}. {target_clause}\n"
                f"구절 A: {target_mention}\n"
                f"구절 B 근거: {owner_clause_index}. {owner_clause}\n"
                f"구절 B: {owner_mention}\n"
                f"{_INSTRUCTION}"
            ),
        },
    ]


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    """Reject duplicate keys instead of silently accepting the last value."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate entity-link JSON key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    """Disallow nonfinite JSON constants accepted by Python's default parser."""
    raise ValueError("nonfinite entity-link JSON value")


def validate_entity_link(raw: str) -> dict[str, str]:
    """Accept only the single finite relation field."""
    if not isinstance(raw, str):
        raise TypeError("entity-link response must be text")
    parsed = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    if not isinstance(parsed, dict) or set(parsed) != {"entity_link"}:
        raise ValueError("entity-link fields differ")
    link = parsed["entity_link"]
    if type(link) is not str or link not in LINKS:
        raise ValueError("entity-link value is unsupported")
    return {"entity_link": link}
