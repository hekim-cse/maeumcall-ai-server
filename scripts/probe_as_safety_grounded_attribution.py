"""Development-only source-anchor check for A/S product-to-hazard attribution.

The model quotes a product and the hazard's owner. The server verifies that
both quotes occur in the selected original clauses before considering a route.
This is a candidate, not a service graph implementation.
"""

from __future__ import annotations

import json
import unicodedata

from scripts.probe_as_safety_clause_index import split_clauses

DIRECT = "safety_action_required"
CONFIRM = "confirming_safety_status"
NORMAL = "collecting_service_request"

PROMPT = (
    "A/S 문의의 원문 문장 번호를 보고 지금 수리를 접수하려는 제품과 위험 현상의 소유 대상을 따로 찾는다. "
    "product_anchor는 접수 제품 이름을 해당 원문 문장에서 연속된 글자로 그대로 복사한다. "
    "hazard_owner_anchor는 위험이 실제로 발생한 물건의 이름을 위험 문장에서 연속된 글자로 그대로 복사한다. "
    "위험의 출처를 알 수 없거나 제품 이름 대신 단순히 '근처'라고만 하면 hazard_owner_anchor는 null이다. "
    "제품의 부품에서 발생한 위험은 그 부품이 속한 제품 이름을 인용할 수 있을 때만 그 이름을 복사한다. "
    "target_relation은 그 위험이 접수 제품에 속하면 current, 명시된 다른 물건이면 other, 출처가 불분명하면 unknown이다. "
    "event_status는 실제 관찰이면 observed, 위험인지 불확실하면 uncertain, 부정·가정·이미 해결된 과거 상태면 nonoccurring이다. "
    "수리 가능 여부를 묻는 후속 질문은 앞서 보고한 위험을 취소하지 않는다. "
    "product_index와 hazard_index는 각각 인용한 근거의 원문 문장 번호다. "
    "인용은 추측하거나 바꿔 쓰지 말고 정확히 원문에 있는 글자만 사용한다. JSON 객체 하나만 반환한다."
)


def model_schema(clause_count: int) -> dict:
    if clause_count < 1:
        raise ValueError("utterance has no source clause")
    return {
        "type": "object",
        "properties": {
            "product_index": {"enum": list(range(1, clause_count + 1))},
            "hazard_index": {"enum": list(range(1, clause_count + 1))},
            "product_anchor": {"type": "string"},
            "hazard_owner_anchor": {"type": ["string", "null"]},
            "target_relation": {"enum": ["current", "other", "unknown"]},
            "event_status": {"enum": ["observed", "uncertain", "nonoccurring"]},
        },
        "required": [
            "product_index",
            "hazard_index",
            "product_anchor",
            "hazard_owner_anchor",
            "target_relation",
            "event_status",
        ],
        "additionalProperties": False,
    }


def _normalized(anchor: str) -> str:
    return "".join(unicodedata.normalize("NFKC", anchor).lower().split())


def _anchor_relation(product: str, owner: str | None) -> str:
    if owner is None:
        return "unknown"
    left, right = _normalized(product), _normalized(owner)
    if right in {"그제품", "이제품", "해당제품", "그것", "이것"}:
        return "unknown"
    if left == right or (min(len(left), len(right)) >= 3 and (left in right or right in left)):
        return "current"
    return "other"


def validate_grounded(raw: str, message: str) -> dict:
    """Reduce model quotes to bounded indices and relations; store no text."""
    clauses = split_clauses(message)
    model_schema(len(clauses))
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or set(parsed) != set(model_schema(len(clauses))["required"]):
        raise ValueError("grounded fields differ")
    product_index, hazard_index = parsed["product_index"], parsed["hazard_index"]
    if any(
        type(index) is not int or not 1 <= index <= len(clauses)
        for index in (product_index, hazard_index)
    ):
        raise ValueError("anchor index outside source clauses")
    product, owner = parsed["product_anchor"], parsed["hazard_owner_anchor"]
    if not isinstance(product, str) or not product.strip():
        raise ValueError("product anchor is empty")
    if owner is not None and (not isinstance(owner, str) or not owner.strip()):
        raise ValueError("hazard owner anchor is empty")
    product_start = clauses[product_index - 1].find(product)
    owner_start = clauses[hazard_index - 1].find(owner) if owner is not None else None
    if product_start < 0 or (owner_start is not None and owner_start < 0):
        raise ValueError("anchor does not occur in selected source clause")
    model_relation, event = parsed["target_relation"], parsed["event_status"]
    if model_relation not in {"current", "other", "unknown"} or event not in {
        "observed",
        "uncertain",
        "nonoccurring",
    }:
        raise ValueError("grounded value outside finite choices")
    return {
        "product_index": product_index,
        "hazard_index": hazard_index,
        "product_start": product_start,
        "product_end": product_start + len(product),
        "owner_start": owner_start,
        "owner_end": owner_start + len(owner) if owner is not None else None,
        "model_relation": model_relation,
        "anchor_relation": _anchor_relation(product, owner),
        "event_status": event,
    }


def route_grounded(decision: dict) -> str:
    """Confirm disagreement instead of turning it into a confident action."""
    if decision["event_status"] == "nonoccurring":
        return NORMAL
    if decision["model_relation"] == decision["anchor_relation"] == "other":
        return NORMAL
    if (
        decision["model_relation"] == decision["anchor_relation"] == "current"
        and decision["event_status"] == "observed"
    ):
        return DIRECT
    return CONFIRM


def journal_schema(message: str) -> dict:
    """Allow only finite source spans and decisions in the exposure journal."""
    clauses = split_clauses(message)
    if not clauses:
        raise ValueError("utterance has no source clause")
    indices = list(range(1, len(clauses) + 1))
    offsets = list(range(max(map(len, clauses)) + 1))
    properties = {
        "product_index": {"enum": indices},
        "hazard_index": {"enum": indices},
        "product_start": {"enum": offsets},
        "product_end": {"enum": offsets},
        "owner_start": {"enum": [None, *offsets]},
        "owner_end": {"enum": [None, *offsets]},
        "model_relation": {"enum": ["current", "other", "unknown"]},
        "anchor_relation": {"enum": ["current", "other", "unknown"]},
        "event_status": {"enum": ["observed", "uncertain", "nonoccurring"]},
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }
