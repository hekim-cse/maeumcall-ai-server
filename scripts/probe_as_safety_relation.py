"""Development-only contract for product-to-hazard attribution in A/S speech.

The model selects source-clause IDs for the product and hazard separately.
This module validates the bounded decision and maps it to a proposed route.
It does not change the service graph or claim safety performance.
"""

from __future__ import annotations

import json

DIRECT = "safety_action_required"
CONFIRM = "confirming_safety_status"
NORMAL = "collecting_service_request"

PROMPT = (
    "A/S 문의에서 사용자가 지금 접수하려는 제품과 안전 위험 사건의 관계를 판단한다. "
    "입력은 번호가 붙은 원문 문장이다. 제품을 식별하는 문장 번호와 위험 사건을 표현한 문장 번호를 각각 고른다. "
    "같은 문장이 둘 다 말하면 두 번호를 같게 둔다. "
    "target_relation은 위험 사건이 현재 접수 제품에 속하면 current, 다른 물건·타인의 경험·자료에만 속하면 other, "
    "소유 대상이 불분명하면 unknown, 위험 사건 자체가 없으면 none이다. "
    "event_status는 현재 발생을 직접 관찰했으면 observed, 발생 자체가 불확실하면 uncertain, "
    "부정·가정·일반 질문이면 nonoccurring, 사건이 없으면 none이다. "
    "수리 가능 여부처럼 후속 조치가 불확실한 것은 위험 발생의 불확실성이 아니다. "
    "실제 위험 보고 뒤에 질문이 붙어도 그 보고를 무시하지 않는다. "
    "다른 제품의 위험과 현재 제품의 일반 고장이 함께 있으면 다른 제품의 위험은 현재 제품의 위험이 아니다. "
    "위험 사건이 없으면 두 번호는 null이고 두 상태는 none이다. JSON 객체 하나만 반환한다."
)


def relation_schema(clause_count: int) -> dict:
    """Constrain both evidence IDs to the server's numbered source clauses."""
    if clause_count < 1:
        raise ValueError("utterance has no source clause")
    indices = [None, *range(1, clause_count + 1)]
    return {
        "type": "object",
        "properties": {
            "product_index": {"enum": indices},
            "hazard_index": {"enum": indices},
            "target_relation": {"enum": ["current", "other", "unknown", "none"]},
            "event_status": {"enum": ["observed", "uncertain", "nonoccurring", "none"]},
        },
        "required": ["product_index", "hazard_index", "target_relation", "event_status"],
        "additionalProperties": False,
    }


def validate_relation(raw: str, clause_count: int) -> dict:
    """Reject invalid indices, enums, and contradictory empty evidence."""
    relation_schema(clause_count)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or set(parsed) != {
        "product_index",
        "hazard_index",
        "target_relation",
        "event_status",
    }:
        raise ValueError("safety relation fields differ")
    product = parsed["product_index"]
    hazard = parsed["hazard_index"]
    target = parsed["target_relation"]
    event = parsed["event_status"]
    for index in (product, hazard):
        if index is not None and (type(index) is not int or not 1 <= index <= clause_count):
            raise ValueError("source index is outside original clauses")
    if target not in {"current", "other", "unknown", "none"}:
        raise ValueError("invalid target relation")
    if event not in {"observed", "uncertain", "nonoccurring", "none"}:
        raise ValueError("invalid event status")
    if hazard is None or target == "none" or event == "none":
        if (product, hazard, target, event) != (None, None, "none", "none"):
            raise ValueError("empty hazard fields disagree")
    elif target in {"current", "other"} and product is None:
        raise ValueError("product attribution lacks source evidence")
    return parsed


def route_relation(decision: dict) -> str:
    """Reserve immediate protection for an observed current-product hazard."""
    target = decision["target_relation"]
    event = decision["event_status"]
    if target == "current" and event == "observed":
        return DIRECT
    if target in {"current", "unknown"} and event in {"observed", "uncertain"}:
        return CONFIRM
    return NORMAL
