"""Two independent owner-oracle questions with a conservative join.

Reviewed A, E, B and occurrence are inputs in this *development* diagnostic.
Gold relation and route must never enter either model request. A model's answer
is a claim, not proof of the physical relationship described by the utterance.
"""

from __future__ import annotations

import json

from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.quotes import anchor_span, split_clauses

ARMS = ("current", "distinct")
DECISIONS = frozenset({"yes", "no", "unknown"})

_QUESTIONS = {
    "current": (
        "위험 사건이 발생한 물건 B가 접수 대상 A 자체이거나, A에 속한 부품·위치이거나, "
        "A를 가리키는 표현인지 판단하세요."
    ),
    "distinct": (
        "위험 사건이 발생한 물건 B가 접수 대상 A와 명시적으로 별개의 물건인지 판단하세요."
    ),
}


def decision_schema() -> dict:
    """Use the same minimal output contract for both independent questions."""
    return {
        "type": "object",
        "properties": {"decision": {"type": "string", "enum": ["yes", "no", "unknown"]}},
        "required": ["decision"],
        "additionalProperties": False,
    }


def decision_messages(case: dict, gold: dict, arm: str) -> list[dict[str, str]]:
    """Provide source and reviewed oracle spans, without gold relation/route.

    This deliberately isolates the relation task; its score must not be called
    an end-to-end safety score because A, E and B were supplied as answers.
    """
    if arm not in ARMS:
        raise ValueError("invalid question arm")
    message = case["user_message"]
    clauses = split_clauses(message)
    target = case["target"]
    event = gold["event_span"]
    owner = gold["hazard_owner_span"]
    occurrence = gold["occurrence"]
    if owner is None or occurrence not in {"observed", "uncertain"}:
        raise ValueError("owner-oracle question requires an actionable event and owner")
    for field, span in (("target", target), ("event_span", event), ("hazard_owner_span", owner)):
        if type(span) is not dict or set(span) != {"clause_index", "quote"}:
            raise ValueError(f"invalid oracle span: {field}")
        anchor_span(span, clauses, field=field)
    source = {
        "user_message": message,
        "target": target,
        "event_span": event,
        "hazard_owner_span": owner,
        "occurrence": occurrence,
    }
    return [
        {
            "role": "system",
            "content": (
                "A/S 발화의 위험 발생 물건 B와 접수 대상 A의 관계를 원문만으로 판단하세요. "
                "yes는 질문의 관계가 명확할 때, no는 반대가 명확할 때, unknown은 "
                "판단 근거가 부족할 때 선택하세요. 원문에 없는 관계를 추측하지 마세요. "
                "decision 한 필드의 JSON 객체만 반환하세요. " + _QUESTIONS[arm]
            ),
        },
        {"role": "user", "content": json.dumps(source, ensure_ascii=False, sort_keys=True)},
    ]


def validate_decision(raw: str) -> str:
    """Reject malformed, duplicate-key and out-of-vocabulary model output."""
    parsed = parse_model_json(raw)
    if type(parsed) is not dict or set(parsed) != {"decision"}:
        raise ValidationError("decision_fields_invalid", "decision")
    decision = parsed["decision"]
    if type(decision) is not str or decision not in DECISIONS:
        raise ValidationError("decision_enum_invalid", "decision")
    return decision


def combine_decisions(current: str | None, distinct: str | None) -> str:
    """Resolve only mutually supporting answers; abstain on all other pairs.

    A missing arm represents a request or contract failure. The caller records
    that failure separately; it must not silently become a positive relation.
    """
    for decision in (current, distinct):
        if decision is not None and decision not in DECISIONS:
            raise ValueError("invalid decision")
    if current == "yes" and distinct == "no":
        return "current"
    if current == "no" and distinct == "yes":
        return "other"
    return "unknown"
