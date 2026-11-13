"""Stage-two relation candidate for development-only A/S safety attribution.

Stage one has already anchored E/B/C to source text. This module keeps the
model's raw relation separate from a conservative effective relation. An exact
quote proves textual provenance, never the truth of a claimed entity link.
"""

from __future__ import annotations

from experiments.as_safety_v2.extraction import _target_clause
from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.quotes import anchor_span, split_clauses

RELATIONS = frozenset({"current", "other", "unknown"})
FIELDS = frozenset({"source_relation", "distinct_evidence_span"})
_SYSTEM = (
    "A/S 발화에서 위험 주체 B와 접수 대상 A의 관계를 판단합니다. 원문에 없는 근거를 만들지 마세요."
)
_INSTRUCTION = (
    "위험 주체 B가 접수 대상 A 또는 A의 부위라면 current, "
    "A와 별개의 물건이라면 other, 명확하지 않으면 unknown을 고르세요. "
    "other를 고른 경우에만 두 물건이 별개임을 보여 주는 원문의 짧은 연속 구절과 "
    "문장 번호를 distinct_evidence_span에 기록하세요. 나머지 관계에서는 null입니다. "
    "앞 단계 인용은 원문에 존재한다는 사실만 확인됐으며 의미상 소속 관계는 확정되지 않았습니다. "
    "JSON 객체에는 source_relation과 distinct_evidence_span 두 키만 넣으세요. "
    "distinct_evidence_span은 clause_index 정수와 quote 문자열을 가진 객체 또는 null입니다. "
    "JSON 객체 하나만 반환하세요."
)


def _evidence(stage1: dict, clauses: tuple[str, ...]) -> dict:
    if type(stage1) is not dict or set(stage1) != {
        "event_span",
        "subject_span",
        "owner_span",
        "owner_kind",
    }:
        raise ValidationError("stage1_fields_invalid", "stage1")
    checked = {}
    for field in ("event_span", "subject_span", "owner_span"):
        item = stage1[field]
        if item is None:
            raise ValidationError("stage1_incomplete", field)
        if type(item) is not dict or not {"clause_index", "quote"} <= set(item):
            raise ValidationError("stage1_span_invalid", field)
        anchored = anchor_span(
            {"clause_index": item["clause_index"], "quote": item["quote"]},
            clauses,
            field=field,
        )
        if item != anchored:
            raise ValidationError("stage1_span_invalid", field)
        checked[field] = anchored
    kind = stage1["owner_kind"]
    if type(kind) is not str or kind not in {"explicit", "implicit_coreference"}:
        raise ValidationError("stage1_owner_kind_invalid", "owner_kind")
    return checked | {"owner_kind": kind}


def stage2_messages(
    user_message: str, stage1: dict, *, product_index: int, target_mention: str
) -> list[dict[str, str]]:
    """Pass A and anchored E/B/C candidates without gold relation or route."""
    clauses = split_clauses(user_message)
    _target_clause(clauses, product_index, target_mention)
    evidence = _evidence(stage1, clauses)
    numbered = "\n".join(f"{index}. {clause}" for index, clause in enumerate(clauses, 1))

    def cited(field: str) -> str:
        span = evidence[field]
        return f"{span['clause_index']}. {span['quote']}"

    return [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": (
                f"원문 전체: {user_message}\n"
                f"번호 문장:\n{numbered}\n"
                f"접수 대상 A: {product_index}. {target_mention}\n"
                f"위험 사건 E 후보: {cited('event_span')}\n"
                f"위험 주체 B 후보: {cited('subject_span')}\n"
                f"소속 대상 C 후보: {cited('owner_span')}\n"
                f"C 연결 유형 후보: {evidence['owner_kind']}\n"
                f"{_INSTRUCTION}"
            ),
        },
    ]


def stage2_schema(user_message: str) -> dict:
    """Bound relation and optional separate-entity evidence to source clauses."""
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
            "source_relation": {"enum": sorted(RELATIONS)},
            "distinct_evidence_span": {"anyOf": [quote, {"type": "null"}]},
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
    """Return raw/effective relation and anchored cue, or a finite error."""
    clauses = split_clauses(user_message)
    _target_clause(clauses, product_index, target_mention)
    evidence = _evidence(stage1, clauses)
    parsed = parse_model_json(raw)
    if type(parsed) is not dict or set(parsed) != FIELDS:
        raise ValidationError("fields_invalid", "stage2")
    relation = parsed["source_relation"]
    if type(relation) is not str or relation not in RELATIONS:
        raise ValidationError("relation_invalid", "source_relation")
    cue = anchor_span(parsed["distinct_evidence_span"], clauses, field="distinct_evidence_span")
    if relation != "other" and cue is not None:
        raise ValidationError("distinct_evidence_inconsistent", "distinct_evidence_span")
    effective = (
        "unknown"
        if relation == "other" and (cue is None or evidence["owner_kind"] != "explicit")
        else relation
    )
    return {
        "model_relation": relation,
        "effective_relation": effective,
        "distinct_evidence_span": cue,
    }
