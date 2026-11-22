"""Ask whether one fixed source candidate is supported as an event source.

This contract checks output shape and source provenance. It cannot verify the
semantic truth of a supported or unsupported relation.
"""

from __future__ import annotations

from dataclasses import dataclass

from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v10.candidate_contract import nominal_catalog
from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate

STATUSES = frozenset({"supported", "unsupported", "insufficient"})
FIELDS = frozenset({"relation_status", "evidence_clause_index"})


@dataclass(frozen=True)
class FixedPair:
    source: str
    clauses: tuple[str, ...]
    event: dict
    candidate: SourceCandidate


def fixed_pair(case: dict, candidate_id: str, kiwi: Kiwi) -> FixedPair:
    """Bind one offered ID using source and reviewed E, never owner gold."""
    source = case["user_message"]
    clauses = split_clauses(source)
    event = anchor_span(case["event_span"], clauses, field="event_span")
    if event is None:
        raise ValueError("event span missing")
    catalog = nominal_catalog(source, kiwi)
    candidate = next((item for item in catalog.candidates if item.id == candidate_id), None)
    if candidate is None:
        raise ValueError("candidate ID not offered")
    return FixedPair(source, clauses, event, candidate)


def messages(pair: FixedPair) -> list[dict[str, str]]:
    numbered = "\n".join(f"{index}. {clause}" for index, clause in enumerate(pair.clauses, 1))
    return [
        {
            "role": "system",
            "content": (
                "제시한 후보 구절이 위험 사건 E의 물리적 출처인지 원문에 근거해 판단하세요. "
                "후보가 원문에 있다는 사실만으로 연결을 확정하지 마세요."
            ),
        },
        {
            "role": "user",
            "content": (
                f"원문 전체: {pair.source}\n번호 문장:\n{numbered}\n"
                f"검수된 위험 사건 E: {pair.event['clause_index']}. {pair.event['quote']}\n"
                f"판단할 후보 B: {pair.candidate.id} | {pair.candidate.clause_index}번 | "
                f"{pair.candidate.quote}\n"
                "relation_status는 supported(원문이 이 후보를 사건의 물리적 출처로 뒷받침함), "
                "unsupported(이 후보는 현상 자체이거나 원문과 모순되어 출처가 될 수 없음), "
                "insufficient(가능성은 있으나 원문만으로 출처를 확정할 수 없음) 중 하나입니다. "
                "supported 또는 unsupported라면 근거가 있는 문장 번호를 "
                "evidence_clause_index에 적으세요. insufficient라면 불확실성을 명시한 문장 번호가 "
                "있을 때만 적고, 없으면 null로 두세요. 문장 번호는 근거 위치를 가리킬 뿐 "
                "관계의 진실성을 자동 증명하지 않습니다. 다른 후보를 제안하거나 접수 제품 소속·"
                "안전 경로를 판단하지 마세요. 두 키의 JSON 객체만 반환하세요."
            ),
        },
    ]


def schema(pair: FixedPair) -> dict:
    return {
        "type": "object",
        "properties": {
            "relation_status": {"enum": sorted(STATUSES)},
            "evidence_clause_index": {
                "anyOf": [{"enum": list(range(1, len(pair.clauses) + 1))}, {"type": "null"}]
            },
        },
        "required": sorted(FIELDS),
        "additionalProperties": False,
    }


def validate_response(raw: str, pair: FixedPair) -> dict:
    parsed = parse_model_json(raw)
    if type(parsed) is not dict or set(parsed) != FIELDS:
        raise ValidationError("fields_invalid", "candidate_relation")
    status = parsed["relation_status"]
    clause_index = parsed["evidence_clause_index"]
    if type(status) is not str or status not in STATUSES:
        raise ValidationError("relation_status_invalid", "relation_status")
    if clause_index is not None and (
        type(clause_index) is not int or not 1 <= clause_index <= len(pair.clauses)
    ):
        raise ValidationError("evidence_clause_invalid", "evidence_clause_index")
    if status != "insufficient" and clause_index is None:
        raise ValidationError("evidence_clause_missing", "evidence_clause_index")
    return {
        "candidate_id": pair.candidate.id,
        "relation_status": status,
        "evidence_clause_index": clause_index,
    }
