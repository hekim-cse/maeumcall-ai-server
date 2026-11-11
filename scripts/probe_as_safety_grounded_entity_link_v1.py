"""Development-only entity link with up to two source-anchored quotes.

Reviewed target and owner mentions are oracle inputs. This contract makes no
model call and cannot prove that an in-text quote supports the chosen relation.
It only checks whether cited text exists at its source clauses and contains
both reviewed mentions; this is not semantic evidence verification.
"""

from __future__ import annotations

import json

from scripts.probe_as_safety_clause_index import split_clauses
from scripts.probe_as_safety_entity_link_v1 import LINKS

_SYSTEM = "두 검수 구절의 개체 관계를 원문 근거와 함께 JSON으로 판단합니다."
_INSTRUCTION = (
    "A와 B가 같은 물건이거나 B가 A의 부품·부위임이 명확하면 same_or_part, "
    "별개의 물건임이 명확하면 distinct_item, 둘 다 입증할 수 없으면 unresolved입니다. "
    "이름이 같아도 다른 사람의 물건이면 별개일 수 있고, 가까운 위치만으로 소속을 "
    "확정하지 마세요. 관계를 뒷받침하는 원문 연속 구절을 evidence 배열에 "
    "문장 번호와 함께 1~2개 인용하세요. 두 문장이 필요하면 각각 인용하세요. "
    "구절 A와 B의 원문 표현이 각각 해당 번호 문장의 인용 안에 포함되어야 합니다. "
    "인용할 관계 근거가 없거나 인용만으로 관계가 불명확하면 unresolved와 빈 "
    "evidence 배열을 반환하세요. 사건 발생 여부나 안전 경로는 판단하지 마세요. "
    'JSON 객체 하나만 반환하세요: {"entity_link":"same_or_part|distinct_item|unresolved",'
    '"evidence":[{"clause_index":1,"quote":"원문 구절"}]}.'
)


def _clauses(user_message: str) -> tuple[str, ...]:
    if not isinstance(user_message, str) or not user_message.strip():
        raise ValueError("utterance must be nonblank text")
    clauses = split_clauses(user_message)
    if not clauses:
        raise ValueError("utterance has no source clause")
    return clauses


def _source_clause(clauses: tuple[str, ...], index: int, mention: str) -> str:
    if (
        type(index) is not int
        or not 1 <= index <= len(clauses)
        or not isinstance(mention, str)
        or not mention.strip()
        or clauses[index - 1].count(mention) != 1
    ):
        raise ValueError("reviewed mention must uniquely anchor its clause")
    return clauses[index - 1]


def grounded_entity_link_schema(user_message: str) -> dict:
    """Bound relation, at most two source IDs, and quote length to the utterance."""
    clauses = _clauses(user_message)
    return {
        "type": "object",
        "properties": {
            "entity_link": {"enum": sorted(LINKS)},
            "evidence": {
                "type": "array",
                "minItems": 0,
                "maxItems": 2,
                "items": {
                    "type": "object",
                    "properties": {
                        "clause_index": {"enum": list(range(1, len(clauses) + 1))},
                        "quote": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": max(map(len, clauses)),
                        },
                    },
                    "required": ["clause_index", "quote"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["entity_link", "evidence"],
        "additionalProperties": False,
    }


def grounded_entity_link_messages(
    user_message: str,
    *,
    target_mention: str,
    product_index: int,
    owner_mention: str,
    owner_clause_index: int,
) -> list[dict[str, str]]:
    """Provide only original text and reviewed target/owner anchors."""
    clauses = _clauses(user_message)
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
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate grounded entity-link JSON key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise ValueError("nonfinite grounded entity-link JSON value")


def _unresolved() -> dict:
    return {"entity_link": "unresolved", "evidence": []}


def validate_grounded_entity_link(
    raw: str,
    user_message: str,
    *,
    target_mention: str,
    product_index: int,
    owner_mention: str,
    owner_clause_index: int,
) -> dict:
    """Reject malformed JSON; abstain unless both mentions have exact anchors.

    Exact quote anchoring checks provenance only. It does not validate whether
    the quoted words semantically prove same/part or distinct-item ownership.
    """
    if not isinstance(raw, str):
        raise TypeError("grounded entity-link response must be text")
    clauses = _clauses(user_message)
    _source_clause(clauses, product_index, target_mention)
    _source_clause(clauses, owner_clause_index, owner_mention)
    parsed = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    if not isinstance(parsed, dict) or set(parsed) != {"entity_link", "evidence"}:
        raise ValueError("grounded entity-link fields differ")
    link = parsed["entity_link"]
    evidence = parsed["evidence"]
    if type(link) is not str or link not in LINKS:
        raise ValueError("grounded entity-link value is unsupported")
    if not isinstance(evidence, list) or len(evidence) > 2:
        raise ValueError("evidence must be a list of at most two quotes")
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {"clause_index", "quote"}:
            raise ValueError("evidence quote fields differ")
        if type(item["clause_index"]) is not int or type(item["quote"]) is not str:
            raise ValueError("evidence quote types differ")
    if link == "unresolved":
        if evidence:
            raise ValueError("unresolved link must not cite evidence")
        return _unresolved()
    if not evidence:
        return _unresolved()
    for item in evidence:
        index = item["clause_index"]
        quote = item["quote"]
        if (
            not 1 <= index <= len(clauses)
            or not quote.strip()
            or quote != quote.strip()
            or clauses[index - 1].count(quote) != 1
        ):
            return _unresolved()
    covers_target = any(
        item["clause_index"] == product_index and target_mention in item["quote"]
        for item in evidence
    )
    covers_owner = any(
        item["clause_index"] == owner_clause_index and owner_mention in item["quote"]
        for item in evidence
    )
    if not (covers_target and covers_owner):
        return _unresolved()
    return {"entity_link": link, "evidence": evidence}
