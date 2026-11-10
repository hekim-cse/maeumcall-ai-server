"""Development-only compact evidence contract for A/S hazard attribution.

One event index supports occurrence and event identity. A separate source index
preserves later corrections. Clause IDs validate shape, not semantic truth.
"""

from __future__ import annotations

import json

DIRECT = "safety_action_required"
CONFIRM = "confirming_safety_status"
NORMAL = "collecting_service_request"

RELATIONS = (
    "current_product",
    "current_part",
    "other_product",
    "location_only",
    "alternative_unknown",
    "unknown",
    "none",
)
STATUSES = ("observed", "uncertain", "nonoccurring", "none")
FIELDS = ("product_index", "event_index", "source_index", "source_relation", "event_status")

PROMPT = (
    "A/S 발화에서 지금 접수하려는 제품과 안전 위험 사건의 관계를 판단한다. "
    "입력의 번호는 원문 문장 번호다. product_index는 접수하려는 제품의 근거 문장, "
    "event_index는 위험 사건의 발생·불확실·가정·부정을 판단하는 근거 문장이다. "
    "위험 사건이 언급됐다면 event_index는 null이 될 수 없다. 위험이 실제 발생했지만 출처가 불확실해도 사건 근거 문장을 고른다. "
    "source_index는 그 위험이 어느 물건에서 비롯됐는지, 또는 뒤 문장에서 출처를 정정·부정한 근거 문장이다. "
    "source_relation은 접수 제품 자체의 위험이면 current_product, 그 제품의 부품이면 current_part, "
    "명시된 다른 제품이면 other_product, 근처·바닥처럼 발생 위치만 알면 location_only, "
    "접수 제품과 다른 제품 중 출처를 모르면 alternative_unknown, 근거가 부족하면 unknown이다. "
    "같은 제품 종류의 다른 기기를 접수 제품과 동일한 실체로 취급하지 않는다. "
    "event_status는 실제 관찰이면 observed, 위험 발생 자체가 불확실하면 uncertain, "
    "부정·가정·현재 해결된 과거 사건이면 nonoccurring이다. 출처 불명은 발생 불명과 구분한다. "
    "수리 가능 여부를 묻는 후속 질문은 앞서 보고한 위험을 취소하지 않는다. "
    "위험 사건 언급이 없으면 세 번호는 모두 null이고 두 상태는 none이다. "
    "근거 번호를 추측해 채우지 말고 원문에 있는 문장만 선택한다. JSON 객체 하나만 반환한다."
)


def compact_relation_schema(clause_count: int) -> dict:
    """Constrain every persisted value to finite source IDs or categories."""
    if clause_count < 1:
        raise ValueError("utterance has no source clause")
    indices = [None, *range(1, clause_count + 1)]
    properties = {
        "product_index": {"enum": indices},
        "event_index": {"enum": indices},
        "source_index": {"enum": indices},
        "source_relation": {"enum": list(RELATIONS)},
        "event_status": {"enum": list(STATUSES)},
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(FIELDS),
        "additionalProperties": False,
    }


def compact_relation_journal_schema(clause_count: int) -> dict:
    """Persist only the finite model decision, never prompt or response text."""
    return compact_relation_schema(clause_count)


def validate_compact_relation(raw: str, clause_count: int) -> dict:
    """Reject missing evidence and incompatible event/source states."""
    schema = compact_relation_schema(clause_count)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or set(parsed) != set(FIELDS):
        raise ValueError("compact relation fields differ")
    for field, value in parsed.items():
        if field.endswith("_index") and value is not None and type(value) is not int:
            raise ValueError("source index must be an integer")
        if value not in schema["properties"][field]["enum"]:
            raise ValueError("compact relation value outside finite choices")

    relation, status = parsed["source_relation"], parsed["event_status"]
    indices = (parsed["product_index"], parsed["event_index"], parsed["source_index"])
    if relation == "none" or status == "none":
        if relation != status or any(index is not None for index in indices):
            raise ValueError("empty event fields disagree")
    else:
        if parsed["product_index"] is None:
            raise ValueError("service target evidence is required")
        if parsed["event_index"] is None:
            raise ValueError("event evidence is required")
        if relation != "unknown" and parsed["source_index"] is None:
            raise ValueError("source relation lacks evidence")
    return parsed


def route_compact_relation(decision: dict) -> str:
    """Keep direct protection exclusive to observed current product hazards."""
    relation, status = decision["source_relation"], decision["event_status"]
    if status in {"none", "nonoccurring"} or relation == "other_product":
        return NORMAL
    if status == "observed" and relation in {"current_product", "current_part"}:
        return DIRECT
    return CONFIRM
