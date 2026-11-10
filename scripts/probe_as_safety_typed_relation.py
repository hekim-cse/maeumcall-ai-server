"""Development-only typed source relation for A/S safety events.

This candidate makes no model call and is not connected to the service graph.
Clause IDs bound its decisions, but cannot prove their semantic correctness.
"""

from __future__ import annotations

import json

DIRECT = "safety_action_required"
CONFIRM = "confirming_safety_status"
NORMAL = "collecting_service_request"

SOURCE_RELATIONS = (
    "current_product",
    "current_part",
    "other_product",
    "location_only",
    "alternative_unknown",
    "unknown",
    "none",
)
EVENT_STATUSES = ("observed", "uncertain", "nonoccurring", "none")
FIELDS = (
    "product_index",
    "event_index",
    "source_index",
    "occurrence_index",
    "source_relation",
    "event_status",
)

PROMPT = (
    "A/S 발화에서 접수하려는 제품, 위험 사건, 위험의 출처를 분리해서 판단한다. "
    "product_index는 접수 제품의 근거 문장, event_index는 위험 현상을 말한 문장, "
    "source_index는 위험 출처의 관계를 판단하는 근거 문장, occurrence_index는 위험의 발생 여부를 판단하는 근거 문장 번호다. "
    "뒤 문장에서 출처를 정정하거나 두 출처 중 어느 쪽인지 모른다고 하면 그 문장을 source_index로 고른다. "
    "source_relation은 위험이 접수 제품에서 직접 발생하면 current_product, 그 제품에 속한 부품에서 발생하면 current_part, "
    "명시된 다른 제품에서 발생하면 other_product, 접수 제품의 근처나 바닥처럼 위치만 알면 location_only, "
    "접수 제품과 다른 제품 중 출처를 알 수 없다고 명시하면 alternative_unknown, 출처를 판단할 근거가 부족하면 unknown이다. "
    "위치에서 관찰되었다는 사실만으로 그 위치에 있는 제품을 출처로 단정하지 않는다. "
    "event_status는 위험 현상을 실제로 관찰했으면 observed, 발생 자체가 불확실하면 uncertain, "
    "부정·가정·이미 해결된 과거 사건이면 nonoccurring이다. 출처가 불명확해도 사건 자체를 관찰했다면 observed이다. "
    "수리 가능 여부를 묻는 후속 질문은 앞서 보고한 위험을 취소하지 않는다. "
    "위험 사건 언급이 없으면 네 문장 번호는 모두 null, 두 상태는 none이다. "
    "원문에 번호가 붙은 문장만 근거로 사용하고 JSON 객체 하나만 반환한다."
)


def typed_relation_schema(clause_count: int) -> dict:
    """Return a finite, text-free decision schema for the numbered utterance."""
    if clause_count < 1:
        raise ValueError("utterance has no source clause")
    indices = [None, *range(1, clause_count + 1)]
    properties = {
        "product_index": {"enum": indices},
        "event_index": {"enum": indices},
        "source_index": {"enum": indices},
        "occurrence_index": {"enum": indices},
        "source_relation": {"enum": list(SOURCE_RELATIONS)},
        "event_status": {"enum": list(EVENT_STATUSES)},
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(FIELDS),
        "additionalProperties": False,
    }


def typed_relation_journal_schema(clause_count: int) -> dict:
    """The exposure journal stores only bounded IDs and decisions, not text."""
    return typed_relation_schema(clause_count)


def validate_typed_relation(raw: str, clause_count: int) -> dict:
    """Validate syntax, finite values, and internally consistent evidence IDs."""
    schema = typed_relation_schema(clause_count)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or set(parsed) != set(FIELDS):
        raise ValueError("typed relation fields differ")
    for field, value in parsed.items():
        if field.endswith("_index") and value is not None and type(value) is not int:
            raise ValueError("source index must be an integer")
        if value not in schema["properties"][field]["enum"]:
            raise ValueError("typed relation value outside finite choices")

    relation, status = parsed["source_relation"], parsed["event_status"]
    indices = tuple(parsed[field] for field in FIELDS[:4])
    if relation == "none" or status == "none":
        if relation != status or any(index is not None for index in indices):
            raise ValueError("empty event fields disagree")
    else:
        if parsed["product_index"] is None:
            raise ValueError("service target evidence is required")
        if parsed["event_index"] is None or parsed["occurrence_index"] is None:
            raise ValueError("event and occurrence evidence are required")
        if relation != "unknown" and parsed["source_index"] is None:
            raise ValueError("source relation lacks evidence")
    return parsed


def route_typed_relation(decision: dict) -> str:
    """Route by event occurrence and typed source relation, never string equality."""
    relation, status = decision["source_relation"], decision["event_status"]
    # An event explicitly attributed to another product is outside this A/S
    # request even if occurrence on that other product is uncertain.
    if status in {"none", "nonoccurring"} or relation == "other_product":
        return NORMAL
    if status == "observed" and relation in {"current_product", "current_part"}:
        return DIRECT
    return CONFIRM
