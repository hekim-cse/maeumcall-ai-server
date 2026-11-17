"""Isolate E→B extraction before asking whether B belongs to A.

The reviewed A, E and occurrence are diagnostic inputs. Quote checks establish
provenance and a narrow direct-link locality constraint, not semantic truth.
Gold owner, relation, edge labels and expected route are never model inputs.
"""

from __future__ import annotations

from experiments.as_safety_v2.evidence_graph import _quote_schema
from experiments.as_safety_v2.extraction import _target_clause
from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.quotes import anchor_span, split_clauses

FIELDS = frozenset({"subject_span", "event_subject_kind", "event_subject_evidence_span"})
KINDS = frozenset({"subject", "location", "implicit", "unresolved"})
OCCURRENCES = frozenset({"observed", "uncertain"})


def _contains(container: dict, item: dict) -> bool:
    """Require the complete quoted item, not a one-character overlap."""
    return (
        container["clause_index"] == item["clause_index"]
        and container["start"] <= item["start"]
        and item["end"] <= container["end"]
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
        raise ValidationError("occurrence_not_callable", "occurrence")
    event = anchor_span(event_span, clauses, field="event_span")
    if event is None:
        raise ValidationError("event_missing", "event_span")
    return clauses, event


def event_owner_schema(user_message: str) -> dict:
    """Constrain only the three fields this atomic step can produce."""
    clauses = split_clauses(user_message)
    quote = _quote_schema(clauses)
    nullable_quote = {"anyOf": [quote, {"type": "null"}]}
    return {
        "type": "object",
        "properties": {
            "subject_span": nullable_quote,
            "event_subject_kind": {"enum": sorted(KINDS)},
            "event_subject_evidence_span": nullable_quote,
        },
        "required": sorted(FIELDS),
        "additionalProperties": False,
    }


def event_owner_messages(
    user_message: str,
    event_span: dict,
    occurrence: str,
    *,
    product_index: int,
    target_mention: str,
) -> list[dict[str, str]]:
    """Ask only for a source-anchored owner and E→B attachment."""
    clauses, event = _inputs(
        user_message,
        event_span,
        occurrence,
        product_index=product_index,
        target_mention=target_mention,
    )
    numbered = "\n".join(f"{index}. {clause}" for index, clause in enumerate(clauses, 1))
    return [
        {
            "role": "system",
            "content": (
                "검수된 A/S 위험 사건 E와 연결되는 물리적 주체 또는 위치 B를 "
                "원문에서 찾으세요. 원문에 없는 사실을 만들지 마세요."
            ),
        },
        {
            "role": "user",
            "content": (
                f"원문 전체: {user_message}\n번호 문장:\n{numbered}\n"
                f"검수된 접수 제품 A: {product_index}. {target_mention}\n"
                f"검수된 위험 사건 E: {event['clause_index']}. {event['quote']}\n"
                f"발생 상태: {occurrence}\n"
                "E와 연결된 주체 또는 위치 B의 짧은 원문 구절을 subject_span에 인용하세요. "
                "event_subject_kind는 subject(명시 주체), location(발생 위치), "
                "implicit(앞선 문맥의 주체), unresolved(확인 불가) 중 하나입니다. "
                "event_subject_evidence_span에는 E와 B를 연결하는 연속 원문 구절을 인용하세요. "
                "implicit이면 앞선 문장의 연결 근거를 인용할 수 있습니다. "
                "주체를 확인할 수 없으면 unresolved와 두 구절 모두 null을 반환하세요. "
                "각 구절은 clause_index와 quote를 가진 객체 또는 null입니다. "
                "B가 접수 제품 A에 속하는지, 최종 안전 경로는 판단하지 마세요. "
                "JSON 객체 하나에 subject_span, event_subject_kind, "
                "event_subject_evidence_span 세 키만 반환하세요."
            ),
        },
    ]


def validate_event_owner(
    raw: str,
    user_message: str,
    event_span: dict,
    occurrence: str,
    *,
    product_index: int,
    target_mention: str,
) -> dict:
    """Validate exact spans and narrow direct locality, without inferring B→A."""
    clauses, event = _inputs(
        user_message,
        event_span,
        occurrence,
        product_index=product_index,
        target_mention=target_mention,
    )
    parsed = parse_model_json(raw)
    if type(parsed) is not dict or set(parsed) != FIELDS:
        raise ValidationError("fields_invalid", "event_owner")
    kind = parsed["event_subject_kind"]
    if type(kind) is not str or kind not in KINDS:
        raise ValidationError("attachment_kind_invalid", "event_subject_kind")
    subject = anchor_span(parsed["subject_span"], clauses, field="subject_span")
    evidence = anchor_span(
        parsed["event_subject_evidence_span"], clauses, field="event_subject_evidence_span"
    )
    resolved = kind != "unresolved"
    if (subject is not None) != resolved or (evidence is not None) != resolved:
        raise ValidationError("attachment_consistency_invalid", "event_subject_kind")
    if kind in {"subject", "location"} and (
        not _contains(evidence, event) or not _contains(evidence, subject)
    ):
        raise ValidationError("direct_attachment_unlinked", "event_subject_evidence_span")
    # An implicit link can cite a prior clause. Its semantic validity is a
    # separate reviewed-label comparison, not an exact-quote contract claim.
    return {
        "event_span": event,
        "subject_span": subject,
        "event_subject_kind": kind,
        "event_subject_evidence_span": evidence,
    }
