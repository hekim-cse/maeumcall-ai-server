"""Development-only two-stage evidence contract for A/S safety attribution.

Stage one finds an event and its occurrence state. Stage two attributes an
observed or uncertain event to the service target. This module makes no model
calls and is not connected to the service graph.
"""

from __future__ import annotations

import json

DIRECT = "safety_action_required"
CONFIRM = "confirming_safety_status"
NORMAL = "collecting_service_request"

EVENT_STATUSES = ("observed", "uncertain", "nonoccurring", "none")
SOURCE_RELATIONS = (
    "current_product",
    "current_part",
    "other_product",
    "location_only",
    "alternative_unknown",
    "unknown",
)
EVENT_FIELDS = ("event_index", "event_status")
SOURCE_FIELDS = ("product_index", "source_index", "source_relation")
JOURNAL_FIELDS = (*EVENT_FIELDS, *SOURCE_FIELDS)

EVENT_PROMPT = (
    "A/S 발화에서 안전 위험 사건의 언급과 발생 상태만 판단한다. "
    "event_index는 위험 현상이 보고되거나 가정·부정된 원문 문장 번호다. "
    "event_status는 실제 관찰이면 observed, 위험인지 불확실하면 uncertain, "
    "부정·가정·이미 해결된 과거 사건이면 nonoccurring, 위험 사건 언급 자체가 없으면 none이다. "
    "출처가 불명확해도 사건 자체를 관찰했다면 observed이다. "
    "수리 가능 여부를 묻는 후속 질문은 앞선 위험 보고를 취소하지 않는다. "
    "none일 때만 event_index를 null로 둔다. 번호가 붙은 원문을 근거로 JSON 객체 하나만 반환한다."
)

SOURCE_PROMPT = (
    "앞 단계에서 지목한 위험 사건이 이번 A/S 접수 제품에 속하는지 판단한다. "
    "입력의 event_index는 이미 선택된 위험 근거 문장 번호이며 이를 변경하지 않는다. "
    "product_index는 접수하려는 제품의 근거 문장 번호, source_index는 위험 출처 또는 "
    "뒤 문장의 출처 정정·불확실성 근거 번호다. "
    "source_relation은 현재 제품에서 직접 발생하면 current_product, 그 제품의 부품에서 "
    "발생하면 current_part, 명시된 다른 제품에서 발생하면 other_product, 제품 근처나 "
    "바닥처럼 위치만 알면 location_only, 현재 제품과 다른 제품 중 출처가 불명확하다고 "
    "명시하면 alternative_unknown, 출처 근거가 부족하면 unknown이다. "
    "같은 제품 이름이 다시 나와도 같은 실체라고 단정하지 않는다. "
    "product_index는 반드시 선택하고, unknown이 아니면 source_index도 반드시 선택한다. "
    "원문 문장 번호만 근거로 JSON 객체 하나만 반환한다."
)


def event_schema(clause_count: int) -> dict:
    """Constrain stage-one output to one event ID and a finite occurrence state."""
    if clause_count < 1:
        raise ValueError("utterance has no source clause")
    return {
        "type": "object",
        "properties": {
            "event_index": {"enum": [None, *range(1, clause_count + 1)]},
            "event_status": {"enum": list(EVENT_STATUSES)},
        },
        "required": list(EVENT_FIELDS),
        "additionalProperties": False,
    }


def source_schema(clause_count: int) -> dict:
    """Require a service target but allow an unknown event source."""
    if clause_count < 1:
        raise ValueError("utterance has no source clause")
    return {
        "type": "object",
        "properties": {
            "product_index": {"enum": list(range(1, clause_count + 1))},
            "source_index": {"enum": [None, *range(1, clause_count + 1)]},
            "source_relation": {"enum": list(SOURCE_RELATIONS)},
        },
        "required": list(SOURCE_FIELDS),
        "additionalProperties": False,
    }


def validate_event(raw: str, clause_count: int) -> dict:
    """Reject invalid or contradictory stage-one evidence."""
    schema = event_schema(clause_count)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or set(parsed) != set(EVENT_FIELDS):
        raise ValueError("event fields differ")
    index, status = parsed["event_index"], parsed["event_status"]
    if index is not None and type(index) is not int:
        raise ValueError("event index must be an integer")
    if index not in schema["properties"]["event_index"]["enum"] or status not in EVENT_STATUSES:
        raise ValueError("event value outside finite choices")
    if (status == "none") != (index is None):
        raise ValueError("event presence and evidence disagree")
    return parsed


def validate_source(raw: str, clause_count: int) -> dict:
    """Reject missing product evidence and unsupported source decisions."""
    schema = source_schema(clause_count)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or set(parsed) != set(SOURCE_FIELDS):
        raise ValueError("source fields differ")
    product, source, relation = (
        parsed["product_index"],
        parsed["source_index"],
        parsed["source_relation"],
    )
    if type(product) is not int or (source is not None and type(source) is not int):
        raise ValueError("source index must be an integer")
    if any(value not in schema["properties"][field]["enum"] for field, value in parsed.items()):
        raise ValueError("source value outside finite choices")
    if relation != "unknown" and source is None:
        raise ValueError("source relation lacks evidence")
    return parsed


def combine_stages(event: dict, source: dict | None) -> dict:
    """Combine validated stages without manufacturing missing evidence."""
    if not isinstance(event, dict) or set(event) != set(EVENT_FIELDS):
        raise ValueError("event decision fields differ")
    if event["event_status"] in {"none", "nonoccurring"}:
        if source is not None:
            raise ValueError("source stage must be skipped")
        return {**event, "product_index": None, "source_index": None, "source_relation": "none"}
    if not isinstance(source, dict) or set(source) != set(SOURCE_FIELDS):
        raise ValueError("source stage is required")
    return {**event, **source}


def route_staged(decision: dict) -> str:
    """Keep direct protection for observed current-product hazards only."""
    if not isinstance(decision, dict) or set(decision) != set(JOURNAL_FIELDS):
        raise ValueError("staged decision fields differ")
    relation, status = decision["source_relation"], decision["event_status"]
    if status in {"none", "nonoccurring"} or relation == "other_product":
        return NORMAL
    if status == "observed" and relation in {"current_product", "current_part"}:
        return DIRECT
    return CONFIRM


def journal_schema(clause_count: int) -> dict:
    """Limit persisted decisions to bounded IDs and status enums only."""
    event = event_schema(clause_count)["properties"]
    source = source_schema(clause_count)["properties"]
    return {
        "type": "object",
        "properties": {
            **event,
            "product_index": {"enum": [None, *source["product_index"]["enum"]]},
            "source_index": source["source_index"],
            "source_relation": {"enum": ["none", *SOURCE_RELATIONS]},
        },
        "required": list(JOURNAL_FIELDS),
        "additionalProperties": False,
    }
