"""A/S hazard-owner link candidate for a conditional Stage2 comparison.

The v2 Stage1 result supplies only candidate event and subject mentions. Exact
quotes establish source provenance, not that the event, owner, or link is true.
"""

from __future__ import annotations

from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.quotes import anchor_span, split_clauses

LINKS = frozenset({"same", "part_of", "coreference", "distinct", "unclear"})
FIELDS = frozenset({"hazard_owner_span", "owner_to_target"})
RELATION = {
    "same": "current",
    "part_of": "current",
    "coreference": "current",
    "distinct": "other",
    "unclear": "unknown",
}

_SYSTEM = (
    "A/S 접수 발화에서 실제 위험 사건이 발생한 물건과 접수 대상의 관계를 판단합니다. "
    "원문에 없는 물건이나 연결 근거를 만들지 마세요."
)
_INSTRUCTION = (
    "위험 사건 E 후보가 일반 고장이나 수리 질문일 수도 있으므로 원문 전체에서 실제 위험 사건을 먼저 확인하세요. "
    "위험 사건이 발생한 물건 P를 원문의 짧은 연속 구절로 hazard_owner_span에 인용하고, "
    "그 물건과 접수 대상 A의 관계를 owner_to_target으로 분류하세요. "
    "같은 물건이면 same, A의 부위·전용 구성품이면 part_of, 앞 문장의 A를 지시하면 coreference, "
    "A와 별개의 물건이면 distinct, 위험 사건이나 소속 관계를 확인할 수 없으면 unclear입니다. "
    "모델이 앞 단계에서 뽑은 E/B는 후보일 뿐이며 정답으로 확정된 것이 아닙니다. "
    "same/part_of/coreference/distinct를 고르면 hazard_owner_span을 반드시 인용하세요. "
    "unclear에서는 물건의 인용이 가능하면 인용하고 찾을 수 없으면 null을 쓰세요. "
    "인용에는 1부터 시작하는 문장 번호 clause_index와 원문 quote를 넣으세요. "
    "최종 안전 경로나 current/other는 출력하지 마세요. "
    "JSON 객체에 hazard_owner_span과 owner_to_target 두 키만 넣으세요."
)


def _target_clause(clauses: tuple[str, ...], product_index: int, target_mention: str) -> str:
    if type(product_index) is not int or not 1 <= product_index <= len(clauses):
        raise ValidationError("target_invalid", "product_index")
    if (
        type(target_mention) is not str
        or not target_mention.strip()
        or target_mention != target_mention.strip()
        or clauses[product_index - 1].count(target_mention) != 1
    ):
        raise ValidationError("target_unanchored", "target_mention")
    return clauses[product_index - 1]


def _stage1_candidates(stage1: dict, clauses: tuple[str, ...]) -> dict[str, dict]:
    if type(stage1) is not dict or not {"event_span", "subject_span"} <= set(stage1):
        raise ValidationError("stage1_fields_invalid", "stage1")
    checked = {}
    for field in ("event_span", "subject_span"):
        item = stage1[field]
        if item is None:
            raise ValidationError("stage1_incomplete", field)
        if type(item) is not dict or set(item) != {
            "clause_index",
            "quote",
            "start",
            "end",
            "quote_sha256",
        }:
            raise ValidationError("stage1_span_invalid", field)
        anchored = anchor_span(
            {"clause_index": item["clause_index"], "quote": item["quote"]},
            clauses,
            field=field,
        )
        if item != anchored:
            raise ValidationError("stage1_span_invalid", field)
        checked[field] = anchored
    return checked


def stage2_messages(
    user_message: str, stage1: dict, *, product_index: int, target_mention: str
) -> list[dict[str, str]]:
    """Give the model A, E/B candidates and source only, never v2 owner C."""
    clauses = split_clauses(user_message)
    target_clause = _target_clause(clauses, product_index, target_mention)
    candidates = _stage1_candidates(stage1, clauses)
    numbered = "\n".join(f"{index}. {clause}" for index, clause in enumerate(clauses, 1))

    def cited(field: str) -> str:
        span = candidates[field]
        return f"{span['clause_index']}. {span['quote']}"

    return [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": (
                f"원문 전체: {user_message}\n"
                f"번호 문장:\n{numbered}\n"
                f"접수 대상 A: {product_index}. {target_mention}\n"
                f"A의 원문 문장: {target_clause}\n"
                f"위험 사건 E 후보: {cited('event_span')}\n"
                f"위험 주체 B 후보: {cited('subject_span')}\n"
                f"{_INSTRUCTION}"
            ),
        },
    ]


def stage2_schema(user_message: str) -> dict:
    """Constrain the two fields and source sentence indices."""
    clauses = split_clauses(user_message)
    quote = {
        "type": "object",
        "properties": {
            "clause_index": {"enum": list(range(1, len(clauses) + 1))},
            "quote": {"type": "string", "minLength": 1, "maxLength": max(map(len, clauses))},
        },
        "required": ["clause_index", "quote"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "hazard_owner_span": {"anyOf": [quote, {"type": "null"}]},
            "owner_to_target": {"enum": sorted(LINKS)},
        },
        "required": sorted(FIELDS),
        "additionalProperties": False,
    }


def validate_stage2(
    raw: str,
    user_message: str,
    stage1: dict,
    *,
    product_index: int,
    target_mention: str,
) -> dict:
    """Check contract and quote provenance; do not claim semantic verification."""
    clauses = split_clauses(user_message)
    _target_clause(clauses, product_index, target_mention)
    _stage1_candidates(stage1, clauses)
    parsed = parse_model_json(raw)
    if type(parsed) is not dict or set(parsed) != FIELDS:
        raise ValidationError("fields_invalid", "stage2")
    link = parsed["owner_to_target"]
    if type(link) is not str or link not in LINKS:
        raise ValidationError("link_invalid", "owner_to_target")
    owner = anchor_span(parsed["hazard_owner_span"], clauses, field="hazard_owner_span")
    if link != "unclear" and owner is None:
        raise ValidationError("owner_required", "hazard_owner_span")
    return {
        "model_link": link,
        "effective_relation": RELATION[link],
        "hazard_owner_span": owner,
    }
