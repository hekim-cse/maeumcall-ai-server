"""Development-only owner evidence probe for A/S hazard source attribution.

Reviewed target/event spans and occurrence status are oracle inputs. The model
must supply a separate source span; no live service or model call uses this file.
"""

from __future__ import annotations

import json

from scripts.probe_as_safety_clause_index import split_clauses

LINK_TO_RELATION = {
    "same_entity": "current",
    "part_or_anaphora": "current",
    "explicit_other": "other",
    "unresolved": "unknown",
}
ACTIVE_STATUSES = frozenset({"observed", "uncertain"})
FIELDS = frozenset({"source_mention", "source_clause_index", "link_kind", "source_relation"})


def owner_evidence_schema(clause_count: int) -> dict:
    """Constrain source IDs and relation categories at generation time."""
    if type(clause_count) is not int or clause_count < 1:
        raise ValueError("utterance has no source clause")
    return {
        "type": "object",
        "properties": {
            "source_mention": {"type": ["string", "null"]},
            "source_clause_index": {"enum": [None, *range(1, clause_count + 1)]},
            "link_kind": {"enum": list(LINK_TO_RELATION)},
            "source_relation": {"enum": ["current", "other", "unknown"]},
        },
        "required": [
            "source_mention",
            "source_clause_index",
            "link_kind",
            "source_relation",
        ],
        "additionalProperties": False,
    }


def owner_evidence_messages(
    user_message: str,
    *,
    product_index: int,
    hazard_index: int,
    event_status: str,
    target_mention: str,
    hazard_event_mention: str,
) -> list[dict[str, str]]:
    """Present reviewed oracle inputs without any owner or relation gold label."""
    if not isinstance(user_message, str):
        raise ValueError("utterance must be text")
    clauses = split_clauses(user_message)
    if not clauses:
        raise ValueError("utterance has no source clause")
    if (
        type(product_index) is not int
        or type(hazard_index) is not int
        or not 1 <= product_index <= len(clauses)
        or not 1 <= hazard_index <= len(clauses)
    ):
        raise ValueError("reviewed evidence index is outside source clauses")
    if event_status not in ACTIVE_STATUSES:
        raise ValueError("reviewed event status is unsupported")
    for mention, index in (
        (target_mention, product_index),
        (hazard_event_mention, hazard_index),
    ):
        if (
            not isinstance(mention, str)
            or not mention.strip()
            or clauses[index - 1].count(mention) != 1
        ):
            raise ValueError("reviewed mention does not uniquely anchor source clause")

    numbered = "\n".join(f"{index}. {clause}" for index, clause in enumerate(clauses, 1))
    prompt = (
        "A/S 접수 대상과 위험 사건의 출처 관계를 판단하세요. 접수 대상·위험 사건의 "
        "구간, 문장 번호, 발생 상태는 사람이 검수한 진단 입력이며 다시 고르지 않습니다.\n"
        f"원문 전체: {user_message}\n"
        f"번호 문장:\n{numbered}\n"
        f"접수 대상 근거 문장: {product_index}. {clauses[product_index - 1]}\n"
        f"검수된 접수 대상 구절: {target_mention}\n"
        f"위험 사건 근거 문장: {hazard_index}. {clauses[hazard_index - 1]}\n"
        f"검수된 위험 사건 구절: {hazard_event_mention}\n"
        f"고정된 위험 발생 상태: {event_status}\n"
        "먼저 위험이 실제로 어느 물건에서 비롯됐는지 원문 전체에서 판단하세요. "
        "source_mention은 위험 출처를 가리키는 원문의 연속 구절 한 개이며, "
        "source_clause_index는 그 구절이 있는 번호 문장입니다. 위험 사건의 위치만으로 "
        "소유 물건을 확정하지 마세요. 뒤따르는 출처 정정과 두 물건 사이의 불확실성도 "
        "고려하세요. 같은 모델명의 다른 사람 제품은 접수 제품과 다른 실체입니다. "
        "접수 제품 자체와 동일하면 link_kind=same_entity, 문맥상 접수 제품에만 "
        "귀속되는 부품·부위·위치 표현 또는 대명사면 part_or_anaphora, 명시된 다른 물건이면 "
        "explicit_other입니다. 출처를 확정할 수 없으면 link_kind=unresolved이고 "
        "source_mention과 source_clause_index는 모두 null입니다. "
        "source_relation은 same_entity/part_or_anaphora면 current, explicit_other면 "
        "other, unresolved면 unknown입니다. 원문에 없는 구절을 만들지 말고 "
        "JSON 객체 하나만 반환하세요."
    )
    return [
        {"role": "system", "content": "위험 출처의 원문 근거와 관계만 JSON 객체로 판단합니다."},
        {"role": "user", "content": prompt},
    ]


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    """Reject duplicate keys before semantic validation."""
    parsed = {}
    for key, value in pairs:
        if key in parsed:
            raise ValueError("owner evidence has duplicate JSON keys")
        parsed[key] = value
    return parsed


def validate_owner_evidence(raw: str, user_message: str) -> dict:
    """Require an anchored owner span and consistent finite relation fields."""
    if not isinstance(user_message, str):
        raise ValueError("utterance must be text")
    clauses = split_clauses(user_message)
    if not clauses:
        raise ValueError("utterance has no source clause")
    parsed = json.loads(raw, object_pairs_hook=_unique_object)
    if not isinstance(parsed, dict) or set(parsed) != FIELDS:
        raise ValueError("owner evidence fields differ")
    kind = parsed["link_kind"]
    if not isinstance(kind, str) or kind not in LINK_TO_RELATION:
        raise ValueError("owner link kind is unsupported")
    relation = parsed["source_relation"]
    if type(relation) is not str or relation != LINK_TO_RELATION[kind]:
        raise ValueError("owner relation disagrees with link kind")
    mention = parsed["source_mention"]
    index = parsed["source_clause_index"]
    if kind == "unresolved":
        if mention is not None or index is not None:
            raise ValueError("unresolved owner must have null source evidence")
    elif (
        not isinstance(mention, str)
        or not mention.strip()
        or type(index) is not int
        or not 1 <= index <= len(clauses)
        or clauses[index - 1].count(mention) != 1
    ):
        raise ValueError("owner evidence is not uniquely anchored to source clause")
    return {
        "source_mention": mention,
        "source_clause_index": index,
        "link_kind": kind,
        "source_relation": relation,
    }
