"""Strict event inventory and per-event owner contract for A/S diagnostics.

Exact quotation establishes provenance, not semantic correctness. This module
does not call a model or change the service's safety routing.
"""

from __future__ import annotations

from experiments.as_safety_v2.extraction import _target_clause
from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.quotes import anchor_span, split_clauses

MAX_EVENTS = 3
OCCURRENCES = frozenset({"observed", "uncertain", "nonoccurring"})
RELATIONS = frozenset({"current", "other", "unknown"})
STAGE1_FIELDS = frozenset({"events", "overflow"})
STAGE2_FIELDS = frozenset({"hazard_owner_span", "owner_to_target"})

_STAGE1_SYSTEM = (
    "A/S 접수 발화에서 관찰·의심·가정·부정 형태로 언급된 구체적 위험 사건을 찾습니다. "
    "일반 고장, 수리 질문, 구체적 사건 언급이 없는 안전 사용법 질문은 제외하세요. "
    "원문에 없는 표현이나 사건을 만들지 마세요."
)
_STAGE1_INSTRUCTION = (
    "원문 전체에서 발화자가 언급한 위험 사건을 문장 순서대로 열거하세요. "
    "사건이 실제로 일어났다면 observed, 일어났는지 불확실하면 uncertain, "
    "특정 제품의 위험을 가정하거나 그 위험이 없었다고 말하면 nonoccurring으로 분류하세요. "
    "과거에 해결돼 현재 위험이 없다고 명시한 사건도 nonoccurring입니다. "
    "접수 대상의 일반 고장보다 다른 물건의 위험 사건이 뒤에 있어도 모두 찾으세요. "
    "각 event_span은 위험 사건을 나타내는 짧은 원문 연속 구절과 1부터 시작하는 문장 번호입니다. "
    "위험 사건이 없으면 빈 목록을 반환하세요. 사건이 3개를 넘으면 앞의 3개를 반환하고 "
    "overflow를 true로 하세요. 임의로 일부 사건을 생략한 채 overflow를 false로 두지 마세요. "
    "위험 발생 물건과 접수 대상의 관계나 최종 안전 경로는 판단하지 마세요. "
    "JSON 객체에 events 배열과 overflow 불리언만 넣으세요."
)
_STAGE2_SYSTEM = (
    "주어진 위험 사건 하나가 어느 물건에서 발생했는지 원문 근거로 확인합니다. "
    "앞 단계가 선택한 사건도 후보이므로 원문과 맞는지 확인하세요."
)
_STAGE2_INSTRUCTION = (
    "해당 사건의 발생 물건 또는 그 부위·위치를 짧은 원문 구절로 인용하세요. "
    "앞 문장의 물건을 가리키는 경우에는 그 연결을 고려하세요. "
    "접수 대상에서 일어난 사건이면 current, 명시된 별개 물건이면 other, "
    "발생 물건이나 연결이 불명확하면 unknown입니다. "
    "current 또는 other라면 hazard_owner_span을 반드시 인용하세요. "
    "이전 단계의 주체·소속 추측이나 검수 정답은 주어지지 않습니다. "
    "최종 안전 경로는 출력하지 마세요. "
    "JSON 객체에 hazard_owner_span과 owner_to_target만 넣으세요."
)


def _numbered(clauses: tuple[str, ...]) -> str:
    return "\n".join(f"{index}. {clause}" for index, clause in enumerate(clauses, 1))


def _quote_schema(clauses: tuple[str, ...]) -> dict:
    return {
        "type": "object",
        "properties": {
            "clause_index": {"enum": list(range(1, len(clauses) + 1))},
            "quote": {"type": "string", "minLength": 1, "maxLength": max(map(len, clauses))},
        },
        "required": ["clause_index", "quote"],
        "additionalProperties": False,
    }


def stage1_messages(
    user_message: str, *, product_index: int, target_mention: str
) -> list[dict[str, str]]:
    clauses = split_clauses(user_message)
    target_clause = _target_clause(clauses, product_index, target_mention)
    return [
        {"role": "system", "content": _STAGE1_SYSTEM},
        {
            "role": "user",
            "content": (
                f"원문 전체: {user_message}\n번호 문장:\n{_numbered(clauses)}\n"
                f"검수된 접수 대상 A: {product_index}. {target_mention}\n"
                f"A의 원문 문장: {target_clause}\n{_STAGE1_INSTRUCTION}"
            ),
        },
    ]


def stage1_schema(user_message: str) -> dict:
    clauses = split_clauses(user_message)
    return {
        "type": "object",
        "properties": {
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "event_span": _quote_schema(clauses),
                        "occurrence": {"enum": sorted(OCCURRENCES)},
                    },
                    "required": ["event_span", "occurrence"],
                    "additionalProperties": False,
                },
                "minItems": 0,
                "maxItems": MAX_EVENTS,
            },
            "overflow": {"type": "boolean"},
        },
        "required": sorted(STAGE1_FIELDS),
        "additionalProperties": False,
    }


def validate_stage1(
    raw: str, user_message: str, *, product_index: int, target_mention: str
) -> dict:
    """Validate shape, source anchors, unique events and textual order."""
    clauses = split_clauses(user_message)
    _target_clause(clauses, product_index, target_mention)
    parsed = parse_model_json(raw)
    if type(parsed) is not dict or set(parsed) != STAGE1_FIELDS:
        raise ValidationError("fields_invalid", "stage1")
    events, overflow = parsed["events"], parsed["overflow"]
    if type(events) is not list or len(events) > MAX_EVENTS:
        raise ValidationError("events_invalid", "events")
    if type(overflow) is not bool or (overflow and len(events) != MAX_EVENTS):
        raise ValidationError("overflow_invalid", "overflow")
    checked: list[dict] = []
    previous_end: tuple[int, int] | None = None
    for index, event in enumerate(events):
        field = f"events[{index}]"
        if type(event) is not dict or set(event) != {"event_span", "occurrence"}:
            raise ValidationError("event_fields_invalid", field)
        occurrence = event["occurrence"]
        if type(occurrence) is not str or occurrence not in OCCURRENCES:
            raise ValidationError("occurrence_invalid", field)
        span = anchor_span(event["event_span"], clauses, field=f"{field}.event_span")
        if span is None:
            raise ValidationError("event_required", field)
        position = (span["clause_index"], span["start"])
        if previous_end is not None and position < previous_end:
            raise ValidationError("event_order_invalid", field)
        previous_end = (span["clause_index"], span["end"])
        checked.append({"event_span": span, "occurrence": occurrence})
    return {"events": checked, "overflow": overflow}


def _checked_event(event: dict, clauses: tuple[str, ...]) -> dict:
    if type(event) is not dict or set(event) != {"event_span", "occurrence"}:
        raise ValidationError("event_fields_invalid", "event")
    occurrence = event["occurrence"]
    if type(occurrence) is not str or occurrence not in OCCURRENCES:
        raise ValidationError("occurrence_invalid", "event")
    span = event["event_span"]
    if type(span) is not dict or set(span) != {
        "clause_index",
        "quote",
        "start",
        "end",
        "quote_sha256",
    }:
        raise ValidationError("event_span_invalid", "event_span")
    anchored = anchor_span(
        {"clause_index": span["clause_index"], "quote": span["quote"]},
        clauses,
        field="event_span",
    )
    if span != anchored:
        raise ValidationError("event_span_invalid", "event_span")
    return event


def stage2_messages(
    user_message: str, event: dict, *, product_index: int, target_mention: str
) -> list[dict[str, str]]:
    clauses = split_clauses(user_message)
    target_clause = _target_clause(clauses, product_index, target_mention)
    checked = _checked_event(event, clauses)
    if checked["occurrence"] == "nonoccurring":
        raise ValidationError("event_not_actionable", "event")
    span = checked["event_span"]
    return [
        {"role": "system", "content": _STAGE2_SYSTEM},
        {
            "role": "user",
            "content": (
                f"원문 전체: {user_message}\n번호 문장:\n{_numbered(clauses)}\n"
                f"접수 대상 A: {product_index}. {target_mention}\n"
                f"A의 원문 문장: {target_clause}\n"
                f"위험 사건 후보: {span['clause_index']}. {span['quote']}\n"
                f"발생 판단 후보: {checked['occurrence']}\n{_STAGE2_INSTRUCTION}"
            ),
        },
    ]


def stage2_schema(user_message: str) -> dict:
    clauses = split_clauses(user_message)
    return {
        "type": "object",
        "properties": {
            "hazard_owner_span": {"anyOf": [_quote_schema(clauses), {"type": "null"}]},
            "owner_to_target": {"enum": sorted(RELATIONS)},
        },
        "required": sorted(STAGE2_FIELDS),
        "additionalProperties": False,
    }


def validate_stage2(
    raw: str,
    user_message: str,
    event: dict,
    *,
    product_index: int,
    target_mention: str,
) -> dict:
    clauses = split_clauses(user_message)
    _target_clause(clauses, product_index, target_mention)
    checked = _checked_event(event, clauses)
    if checked["occurrence"] == "nonoccurring":
        raise ValidationError("event_not_actionable", "event")
    parsed = parse_model_json(raw)
    if type(parsed) is not dict or set(parsed) != STAGE2_FIELDS:
        raise ValidationError("fields_invalid", "stage2")
    relation = parsed["owner_to_target"]
    if type(relation) is not str or relation not in RELATIONS:
        raise ValidationError("relation_invalid", "owner_to_target")
    owner = anchor_span(parsed["hazard_owner_span"], clauses, field="hazard_owner_span")
    if relation != "unknown" and owner is None:
        raise ValidationError("owner_required", "hazard_owner_span")
    return {"hazard_owner_span": owner, "owner_to_target": relation}


def route_for_events(
    events: list[dict],
    relations: list[str | None],
    *,
    overflow: bool = False,
    failed: bool = False,
) -> str:
    """Apply safety-first route precedence to validated event decisions.

    A failed call may leave an actionable event without a relation. The caller
    must pass failed=True, which yields confirmation unless a confirmed current
    observed hazard already requires immediate safety action.
    """
    if type(events) is not list or type(relations) is not list or len(events) != len(relations):
        raise ValueError("event decision alignment differs")
    if type(overflow) is not bool or type(failed) is not bool:
        raise ValueError("route flags invalid")
    unknown = overflow or failed
    observed_current = False
    for event, relation in zip(events, relations, strict=True):
        if type(event) is not dict or event.get("occurrence") not in OCCURRENCES:
            raise ValueError("event occurrence invalid")
        occurrence = event["occurrence"]
        if occurrence == "nonoccurring":
            if relation is not None:
                raise ValueError("nonoccurring event has relation")
            continue
        if relation is None:
            if not failed:
                raise ValueError("actionable event lacks relation")
            unknown = True
        elif type(relation) is not str or relation not in RELATIONS:
            raise ValueError("event relation invalid")
        elif occurrence == "observed" and relation == "current":
            observed_current = True
        elif relation == "unknown" or (occurrence == "uncertain" and relation == "current"):
            unknown = True
    if observed_current:
        return "safety_action_required"
    return "confirming_safety_status" if unknown else "collecting_service_request"
