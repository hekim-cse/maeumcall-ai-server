"""Development-only, source-anchored E→B→A evidence contract.

E (the reviewed event) and A (the reviewed service target) are diagnostic
inputs. The model must attach an utterance span B to E, then describe a typed
B→A edge. Exact quotes prove only textual provenance; neither anchoring nor
an edge label proves that the semantic attachment or entity relation is true.
Those two stages must be scored against separately reviewed answers.
"""

from __future__ import annotations

from experiments.as_safety_v2.extraction import _target_clause
from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.quotes import anchor_span, split_clauses

ATTACHMENT_KINDS = frozenset({"subject", "location", "implicit", "unresolved"})
EDGE_KINDS = frozenset(
    {"same_entity", "part_of", "located_at", "coreference", "distinct", "unresolved"}
)
OCCURRENCES = frozenset({"observed", "uncertain"})
FIELDS = frozenset(
    {
        "subject_span",
        "event_subject_kind",
        "event_subject_evidence_span",
        "target_edge_kind",
        "target_edge_evidence_span",
    }
)


def _inputs(
    user_message: str,
    event_span: dict,
    occurrence: str,
    *,
    product_index: int,
    target_mention: str,
) -> tuple[tuple[str, ...], dict]:
    clauses = split_clauses(user_message)
    _target_clause(clauses, product_index, target_mention)
    if type(occurrence) is not str or occurrence not in OCCURRENCES:
        raise ValidationError("occurrence_invalid", "occurrence")
    event = anchor_span(event_span, clauses, field="event_span")
    if event is None:
        raise ValidationError("event_missing", "event_span")
    return clauses, event


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


def _overlaps(left: dict, right: dict) -> bool:
    """Check source locality only, without inferring a semantic relation."""
    return left["clause_index"] == right["clause_index"] and max(
        left["start"], right["start"]
    ) < min(left["end"], right["end"])


def evidence_graph_schema(user_message: str) -> dict:
    """Constrain the response shape, leaving semantic consistency to validation."""
    clauses = split_clauses(user_message)
    quote = _quote_schema(clauses)
    nullable = {"anyOf": [quote, {"type": "null"}]}
    return {
        "type": "object",
        "properties": {
            "subject_span": nullable,
            "event_subject_kind": {"enum": sorted(ATTACHMENT_KINDS)},
            "event_subject_evidence_span": nullable,
            "target_edge_kind": {"enum": sorted(EDGE_KINDS)},
            "target_edge_evidence_span": nullable,
        },
        "required": sorted(FIELDS),
        "additionalProperties": False,
    }


def evidence_graph_messages(
    user_message: str,
    event_span: dict,
    occurrence: str,
    *,
    product_index: int,
    target_mention: str,
) -> list[dict[str, str]]:
    """Supply only source, reviewed A, and reviewed E/occurrence to the model."""
    clauses, event = _inputs(
        user_message,
        event_span,
        occurrence,
        product_index=product_index,
        target_mention=target_mention,
    )
    numbered = "\n".join(f"{i}. {clause}" for i, clause in enumerate(clauses, 1))
    return [
        {
            "role": "system",
            "content": (
                "A/S 위험 사건 E의 물리적 발생 주체 B와 접수 제품 A의 연결 근거를 "
                "원문에서 각각 찾으세요. 원문에 없는 사실을 만들지 마세요."
            ),
        },
        {
            "role": "user",
            "content": (
                f"원문 전체: {user_message}\n번호 문장:\n{numbered}\n"
                f"접수 제품 A: {product_index}. {target_mention}\n"
                f"검수된 위험 사건 E: {event['clause_index']}. {event['quote']}\n"
                f"E의 발생 상태: {occurrence}\n"
                "먼저 E가 발생한 주체 B를 짧은 원문 구절로 인용하고, E→B 연결을 "
                "subject(명시 주체), location(발생 위치), implicit(문맥 연결), "
                "unresolved(확인 불가) 중 하나로 분류하세요. 그 연결을 뒷받침하는 "
                "원문 구절을 event_subject_evidence_span에 인용하세요. "
                "다음 B→A 관계를 same_entity(같은 물건), part_of(부품·표면), "
                "located_at(A의 안·뒤 등 위치), coreference(지시어가 A를 가리킴), "
                "distinct(별개 물건), unresolved(확인 불가) "
                "중 하나로 분류하고 target_edge_evidence_span에 연결 근거를 인용하세요. "
                "distinct라면 그 근거 구절에 B가 포함되어야 합니다. "
                "구절이 없거나 관계가 불명확하면 unresolved와 null을 사용하세요. "
                "인용만으로 의미 관계가 증명되지는 않습니다. 최종 안전 경로는 결정하지 마세요. "
                "JSON 객체 하나에 subject_span, event_subject_kind, "
                "event_subject_evidence_span, target_edge_kind, "
                "target_edge_evidence_span 다섯 키만 반환하세요. 각 구절은 "
                "clause_index와 quote를 가진 객체 또는 null입니다."
            ),
        },
    ]


def validate_evidence_graph(
    raw: str,
    user_message: str,
    event_span: dict,
    occurrence: str,
    *,
    product_index: int,
    target_mention: str,
) -> dict:
    """Validate provenance and field consistency, then derive a relation.

    The returned relation is a *claimed* relation. The validator cannot check
    whether a source-anchored quote entails the claimed semantic edge.
    """
    clauses, event = _inputs(
        user_message,
        event_span,
        occurrence,
        product_index=product_index,
        target_mention=target_mention,
    )
    parsed = parse_model_json(raw)
    if type(parsed) is not dict or set(parsed) != FIELDS:
        raise ValidationError("fields_invalid", "evidence_graph")
    attachment = parsed["event_subject_kind"]
    edge = parsed["target_edge_kind"]
    if type(attachment) is not str or attachment not in ATTACHMENT_KINDS:
        raise ValidationError("attachment_kind_invalid", "event_subject_kind")
    if type(edge) is not str or edge not in EDGE_KINDS:
        raise ValidationError("edge_kind_invalid", "target_edge_kind")
    spans = {
        field: anchor_span(parsed[field], clauses, field=field)
        for field in (
            "subject_span",
            "event_subject_evidence_span",
            "target_edge_evidence_span",
        )
    }
    subject_present = spans["subject_span"] is not None
    attachment_evidence_present = spans["event_subject_evidence_span"] is not None
    attachment_resolved = attachment != "unresolved"
    if subject_present != attachment_resolved or attachment_evidence_present != attachment_resolved:
        raise ValidationError("attachment_consistency_invalid", "event_subject_kind")
    if attachment_resolved:
        cue = spans["event_subject_evidence_span"]
        subject = spans["subject_span"]
        if not _overlaps(cue, event):
            raise ValidationError("event_attachment_unlinked", "event_subject_evidence_span")
        if attachment in {"subject", "location"} and not _overlaps(cue, subject):
            raise ValidationError("subject_attachment_unlinked", "subject_span")
    if edge == "unresolved":
        if spans["target_edge_evidence_span"] is not None:
            raise ValidationError("edge_consistency_invalid", "target_edge_evidence_span")
    elif not subject_present or spans["target_edge_evidence_span"] is None:
        raise ValidationError("edge_consistency_invalid", "target_edge_kind")
    elif edge == "distinct" and not (
        spans["target_edge_evidence_span"]["clause_index"] == spans["subject_span"]["clause_index"]
        and spans["target_edge_evidence_span"]["start"] <= spans["subject_span"]["start"]
        and spans["subject_span"]["end"] <= spans["target_edge_evidence_span"]["end"]
    ):
        # The cue must cite all of B. This does not prove that B and A
        # are semantically distinct; reviewed edge scoring remains necessary.
        raise ValidationError("distinct_subject_unlinked", "target_edge_evidence_span")
    relation = (
        "current"
        if edge in {"same_entity", "part_of", "located_at", "coreference"}
        else "other"
        if edge == "distinct"
        else "unknown"
    )
    return {
        "event_span": event,
        **spans,
        "event_subject_kind": attachment,
        "target_edge_kind": edge,
        "effective_relation": relation,
    }


def route_for(occurrence: str, relation: str) -> str:
    """Return the existing conservative route for a validated relation."""
    if type(occurrence) is not str or occurrence not in OCCURRENCES:
        raise ValidationError("occurrence_invalid", "occurrence")
    if type(relation) is not str or relation not in {"current", "other", "unknown"}:
        raise ValidationError("relation_invalid", "relation")
    if relation == "other":
        return "collecting_service_request"
    if relation == "current" and occurrence == "observed":
        return "safety_action_required"
    return "confirming_safety_status"


def aggregate_event_routes(routes: list[str] | tuple[str, ...]) -> str:
    """Combine per-event routes without allowing one `other` to hide a hazard."""
    allowed = {
        "safety_action_required",
        "confirming_safety_status",
        "collecting_service_request",
    }
    if type(routes) not in (list, tuple) or not routes:
        raise ValidationError("routes_invalid", "routes")
    if any(type(route) is not str or route not in allowed for route in routes):
        raise ValidationError("route_invalid", "routes")
    if "safety_action_required" in routes:
        return "safety_action_required"
    if "confirming_safety_status" in routes:
        return "confirming_safety_status"
    return "collecting_service_request"


def decide_with_contract_fallback(
    raw: str,
    user_message: str,
    event_span: dict,
    occurrence: str,
    *,
    product_index: int,
    target_mention: str,
) -> dict:
    """Map malformed output to confirmation without claiming semantic safety."""
    try:
        result = validate_evidence_graph(
            raw,
            user_message,
            event_span,
            occurrence,
            product_index=product_index,
            target_mention=target_mention,
        )
    except ValidationError as issue:
        return {
            "effective_relation": "unknown",
            "route": "confirming_safety_status",
            "error_code": issue.code,
            "error_field": issue.field,
        }
    return result | {
        "route": route_for(occurrence, result["effective_relation"]),
        "error_code": None,
        "error_field": None,
    }
