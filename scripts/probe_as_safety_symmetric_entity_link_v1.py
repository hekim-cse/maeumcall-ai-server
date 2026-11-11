"""Development-only symmetric entity link between two reviewed mentions.

The model receives the original utterance and oracle target/owner mentions,
not the gold relation or occurrence status. Two answers from one completion
may share a bias; their consistency is not semantic proof of entity identity.
No model call or service integration occurs in this module.
"""

from __future__ import annotations

import json

from scripts.probe_as_safety_grounded_entity_link_v1 import _clauses, _source_clause

ANSWERS = frozenset({"yes", "no", "uncertain"})
LINK_DECISIONS = {
    ("yes", "no"): "same_or_part",
    ("no", "yes"): "distinct_item",
}

_SYSTEM = "검수된 두 구절의 개체 관계에 관한 두 명제를 각각 판단하고 JSON으로 답합니다."
_INSTRUCTION = (
    "두 명제를 각각 원문만으로 판단하세요. "
    "same_or_part: 구절 A와 B가 같은 물건이거나 B가 A의 소속 부품·부위인가요? "
    "distinct_item: 구절 B가 A와 별개의 물건에 속하나요? "
    "각 명제에 yes, no, uncertain 중 하나만 답하세요. 원문에서 판단 근거가 "
    "부족하면 uncertain을 사용하세요. 이름이 같은 제품도 다른 사람의 물건이면 "
    "별개일 수 있고, 가까이 있는 위치만으로 소속을 확정하지 마세요. "
    "두 답이 충돌하면 서버가 관계를 보류합니다. 위험 발생 여부·안전 경로는 판단하지 "
    '마세요. JSON 객체 하나만 반환하세요: {"same_or_part":"yes|no|uncertain",'
    '"distinct_item":"yes|no|uncertain"}.'
)


def symmetric_entity_link_schema() -> dict:
    """Constrain both proposition answers to finite, text-free values."""
    return {
        "type": "object",
        "properties": {
            "same_or_part": {"enum": sorted(ANSWERS)},
            "distinct_item": {"enum": sorted(ANSWERS)},
        },
        "required": ["same_or_part", "distinct_item"],
        "additionalProperties": False,
    }


def symmetric_entity_link_messages(
    user_message: str,
    *,
    target_mention: str,
    product_index: int,
    owner_mention: str,
    owner_clause_index: int,
) -> list[dict[str, str]]:
    """Supply only the utterance and reviewed A/B mention anchors."""
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
            raise ValueError("duplicate symmetric entity-link JSON key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise ValueError("nonfinite symmetric entity-link JSON value")


def validate_symmetric_entity_link(raw: str) -> dict[str, str]:
    """Retain raw finite answers; map only opposing certainties to a relation."""
    if not isinstance(raw, str):
        raise TypeError("symmetric entity-link response must be text")
    parsed = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    if not isinstance(parsed, dict) or set(parsed) != {"same_or_part", "distinct_item"}:
        raise ValueError("symmetric entity-link fields differ")
    same, distinct = parsed["same_or_part"], parsed["distinct_item"]
    if type(same) is not str or same not in ANSWERS:
        raise ValueError("same_or_part answer is unsupported")
    if type(distinct) is not str or distinct not in ANSWERS:
        raise ValueError("distinct_item answer is unsupported")
    return {
        "same_or_part_answer": same,
        "distinct_item_answer": distinct,
        "entity_link": LINK_DECISIONS.get((same, distinct), "unresolved"),
    }
