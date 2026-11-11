"""Development-only oracle-input probe for A/S hazard source attribution.

Reviewed target/event clause IDs and occurrence status are supplied as inputs.
They are not available to the live service, and this module makes no model call.
"""

from __future__ import annotations

import json

from scripts.probe_as_safety_clause_index import split_clauses

DIRECT = "safety_action_required"
CONFIRM = "confirming_safety_status"
NORMAL = "collecting_service_request"
RELATIONS = frozenset({"current", "other", "unknown"})
EVENT_STATUSES = frozenset({"observed", "uncertain", "nonoccurring"})


def relation_schema() -> dict:
    """Require exactly one finite source relation from the model."""
    return {
        "type": "object",
        "properties": {"source_relation": {"enum": sorted(RELATIONS)}},
        "required": ["source_relation"],
        "additionalProperties": False,
    }


def relation_messages(
    user_message: str,
    *,
    product_index: int,
    hazard_index: int,
    event_status: str,
    target_mention: str,
    hazard_event_mention: str,
) -> list[dict[str, str]]:
    """Present the whole utterance and reviewed clause IDs without the gold relation."""
    clauses = split_clauses(user_message)
    if not clauses:
        raise ValueError("utterance has no source clause")
    if (
        type(product_index) is not int
        or type(hazard_index) is not int
        or not 1 <= product_index <= len(clauses)
        or not 1 <= hazard_index <= len(clauses)
    ):
        raise ValueError("reviewed evidence index is outside source clauses")
    if event_status not in EVENT_STATUSES:
        raise ValueError("reviewed event status is unsupported")
    if (
        not isinstance(target_mention, str)
        or not target_mention.strip()
        or target_mention not in clauses[product_index - 1]
        or not isinstance(hazard_event_mention, str)
        or not hazard_event_mention.strip()
        or hazard_event_mention not in clauses[hazard_index - 1]
    ):
        raise ValueError("reviewed target or event mention is not in its source clause")

    numbered = "\n".join(f"{index}. {clause}" for index, clause in enumerate(clauses, 1))
    prompt = (
        "A/S 접수 대상과 위험 사건의 출처 관계만 판단하세요. 아래 근거 문장 번호와 "
        "위험 발생 상태는 사람이 검수해 고정한 진단 입력이며, 모델이 다시 고르지 않습니다.\n"
        f"원문 전체: {user_message}\n"
        f"번호 문장:\n{numbered}\n"
        f"접수 대상 근거 문장: {product_index}. {clauses[product_index - 1]}\n"
        f"검수된 접수 대상 구절: {target_mention}\n"
        f"위험 사건 근거 문장: {hazard_index}. {clauses[hazard_index - 1]}\n"
        f"검수된 위험 사건 구절: {hazard_event_mention}\n"
        f"고정된 위험 발생 상태: {event_status}\n"
        "source_relation은 위험이 현재 접수 대상 제품이나 그 부품에 속하면 current, "
        "명시된 다른 제품에 속하면 other, 출처를 확정할 수 없으면 unknown입니다. "
        "한 문장에 접수 대상과 다른 제품이 함께 나올 수 있으므로 문장 번호가 같다는 "
        "이유만으로 같은 제품이라고 판단하지 마세요. 구절에 포함된 제품 이름과 "
        "원문 전체의 지시 관계를 확인하세요. 발생 위치만 알거나 제품 사이의 "
        "귀속이 불명확한 경우도 unknown입니다. 원문 전체의 뒤따르는 정정과 부정을 "
        "고려하세요. 접수 대상이나 위험 사건의 문장 번호를 출력하지 마세요. "
        'JSON 객체 하나만 반환하세요: {"source_relation":"current|other|unknown"}.'
    )
    return [
        {"role": "system", "content": "위험 사건의 출처 관계만 JSON 객체로 판단합니다."},
        {"role": "user", "content": prompt},
    ]


def validate_relation(raw: str) -> dict[str, str]:
    """Reject missing, extra, or unsupported model decisions."""

    def unique_object(pairs: list[tuple[str, object]]) -> dict:
        parsed = {}
        for key, value in pairs:
            if key in parsed:
                raise ValueError("oracle relation has duplicate JSON keys")
            parsed[key] = value
        return parsed

    parsed = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(parsed, dict) or set(parsed) != {"source_relation"}:
        raise ValueError("oracle relation fields differ")
    relation = parsed["source_relation"]
    if not isinstance(relation, str) or relation not in RELATIONS:
        raise ValueError("oracle relation is outside finite choices")
    return {"source_relation": relation}


def route_with_reviewed_event(decision: dict[str, str], *, event_status: str) -> str:
    """Diagnostic-only route using the reviewed occurrence status, not a live decision."""
    if not isinstance(decision, dict) or set(decision) != {"source_relation"}:
        raise ValueError("oracle relation fields differ")
    relation = decision["source_relation"]
    if relation not in RELATIONS or event_status not in EVENT_STATUSES:
        raise ValueError("oracle relation or reviewed event status is unsupported")
    if event_status == "nonoccurring" or relation == "other":
        return NORMAL
    if event_status == "observed" and relation == "current":
        return DIRECT
    return CONFIRM
