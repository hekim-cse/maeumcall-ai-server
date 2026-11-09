"""Development-only focused entailment probe for current-product hazard claims."""

from __future__ import annotations

import json

DIRECT = "safety_action_required"
CONFIRM = "confirming_safety_status"
NORMAL = "collecting_service_request"

PROMPT = (
    "A/S 접수 발화가 '지금 수리 접수하려는 바로 그 제품에서 안전 위험이 실제 발생했다'는 명제를 뒷받침하는지 판단한다. "
    "먼저 수리 접수 대상을 찾고, 위험 현상의 주어가 그 제품인지 다른 물건인지 구별한다. "
    "위험 문장에 다른 물건의 이름이 명시되면 그 위험을 접수 제품으로 옮기지 않는다. "
    "'그 제품' 같은 지시어는 앞 문장의 대상을 확인한 뒤 연결한다. "
    "발생 자체가 아니라 수리 가능 여부를 묻는 질문은 실제 위험 보고를 취소하지 않는다. "
    "설명서·타인 경험·가정·명시적 부정은 현재 제품의 실제 발생 근거가 아니다. "
    "claim은 현재 제품의 실제 위험 보고가 분명하면 entailed, 다른 출처나 미발생이 분명하면 contradicted, "
    "소유 대상 또는 발생 여부가 불명확하면 uncertain이다. "
    "reason은 same_product_observed, other_source, nonoccurring, uncertain 중 하나다. "
    "위험 근거 문장 번호 하나를 고르되 위험 표현 자체가 없으면 null이다. JSON 객체 하나만 반환한다."
)


def entailment_schema(clause_count: int) -> dict:
    if clause_count < 1:
        raise ValueError("utterance has no source clause")
    return {
        "type": "object",
        "properties": {
            "hazard_index": {"enum": [None, *range(1, clause_count + 1)]},
            "claim": {"enum": ["entailed", "contradicted", "uncertain"]},
            "reason": {
                "enum": ["same_product_observed", "other_source", "nonoccurring", "uncertain"]
            },
        },
        "required": ["hazard_index", "claim", "reason"],
        "additionalProperties": False,
    }


def validate_entailment(raw: str, clause_count: int) -> dict:
    entailment_schema(clause_count)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or set(parsed) != {"hazard_index", "claim", "reason"}:
        raise ValueError("entailment fields differ")
    index, claim, reason = (parsed[key] for key in ("hazard_index", "claim", "reason"))
    if index is not None and (type(index) is not int or not 1 <= index <= clause_count):
        raise ValueError("hazard index outside source clauses")
    if (claim, reason) not in {
        ("entailed", "same_product_observed"),
        ("contradicted", "other_source"),
        ("contradicted", "nonoccurring"),
        ("uncertain", "uncertain"),
    }:
        raise ValueError("claim and reason disagree")
    if index is None and claim != "contradicted":
        raise ValueError("positive or uncertain claim lacks hazard evidence")
    return parsed


def route_entailment(decision: dict) -> str:
    return {
        "entailed": DIRECT,
        "uncertain": CONFIRM,
        "contradicted": NORMAL,
    }[decision["claim"]]
