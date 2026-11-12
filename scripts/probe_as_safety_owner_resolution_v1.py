"""Development-only two-stage A/S owner-resolution contracts.

Stage one extracts candidate E (hazard event), B (hazard subject), C (the
subject's antecedent/owner), and optional connecting cues. Only the reviewed
service target A is supplied as an oracle. Stage two classifies the relation
using validated stage-one candidates. Exact quotes and a model-selected
distinct cue prove text provenance, not the semantic truth of ownership.
No model call or service integration occurs here.
"""

from __future__ import annotations

import hashlib
import json

from scripts.probe_as_safety_clause_index import split_clauses
from scripts.probe_as_safety_grounded_entity_link_v1 import _source_clause

OWNER_KINDS = frozenset({"explicit", "implicit_coreference", "unresolved"})
RELATIONS = frozenset({"current", "other", "unknown"})
STAGE1_FIELDS = frozenset(
    {"event_span", "subject_span", "owner_span", "owner_kind", "cue_spans", "distinct_cue_index"}
)

_STAGE1_SYSTEM = "A/S 발화의 위험 사건·주체·소속 후보를 원문 구절로 추출합니다."
_STAGE1_INSTRUCTION = (
    "검수된 A는 이번 A/S 접수 대상입니다. E는 원문에 언급된 위험 사건, B는 그 위험의 "
    "물리적 주체, C는 B가 속한 물건 또는 B를 지칭하는 표현의 선행사입니다. "
    "E/B/C 각각 원문에 연속해서 있는 가장 짧은 구절과 문장 번호를 제시하세요. "
    "찾을 수 없으면 null을 쓰세요. C는 다른 제품의 명시적 소유 대상이면 explicit, "
    "앞 문장의 대상·부위를 후속 표현이 가리키면 implicit_coreference, 확정하기 "
    "어려우면 unresolved입니다. implicit_coreference의 C에는 원문 선행사 구절을 "
    "인용할 수 있습니다. 관계를 잇는 추가 단서가 있다면 cue_spans에 최대 2개 인용하고, "
    "그중 B가 A와 별개 물건이라는 후보 근거가 있으면 distinct_cue_index에 배열의 "
    "0부터 시작하는 위치를 적으세요. 이는 후보 단서 선택이며 관계 정답의 증명이 "
    "아닙니다. 위험 발생 상태나 접수 대상과의 최종 관계는 판단하지 마세요. "
    'JSON 객체 하나만 반환하세요: {"event_span":{"clause_index":1,"quote":"원문"}|null,'
    '"subject_span":{"clause_index":1,"quote":"원문"}|null,'
    '"owner_span":{"clause_index":1,"quote":"원문"}|null,'
    '"owner_kind":"explicit|implicit_coreference|unresolved",'
    '"cue_spans":[{"clause_index":1,"quote":"원문"}],"distinct_cue_index":0|null}.'
)
_STAGE2_SYSTEM = "검증된 원문 구절을 참고해 위험 주체와 접수 대상의 관계 하나만 판단합니다."


def _clauses(user_message: str) -> tuple[str, ...]:
    if not isinstance(user_message, str) or not user_message.strip():
        raise ValueError("utterance must be nonblank text")
    clauses = split_clauses(user_message)
    if not clauses:
        raise ValueError("utterance has no source clause")
    return clauses


def _quote_schema(clause_count: int, max_length: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "clause_index": {"enum": list(range(1, clause_count + 1))},
            "quote": {"type": "string", "minLength": 1, "maxLength": max_length},
        },
        "required": ["clause_index", "quote"],
        "additionalProperties": False,
    }


def owner_resolution_stage1_schema(user_message: str) -> dict:
    """Bound model output to indexed source quotes and finite owner kinds."""
    clauses = _clauses(user_message)
    quote = _quote_schema(len(clauses), max(map(len, clauses)))
    return {
        "type": "object",
        "properties": {
            "event_span": {"anyOf": [quote, {"type": "null"}]},
            "subject_span": {"anyOf": [quote, {"type": "null"}]},
            "owner_span": {"anyOf": [quote, {"type": "null"}]},
            "owner_kind": {"enum": sorted(OWNER_KINDS)},
            "cue_spans": {"type": "array", "minItems": 0, "maxItems": 2, "items": quote},
            "distinct_cue_index": {"enum": [None, 0, 1]},
        },
        "required": sorted(STAGE1_FIELDS),
        "additionalProperties": False,
    }


def owner_resolution_stage1_messages(
    user_message: str, *, product_index: int, target_mention: str
) -> list[dict[str, str]]:
    """Expose original utterance and reviewed A only; B/C remain hidden."""
    clauses = _clauses(user_message)
    target_clause = _source_clause(clauses, product_index, target_mention)
    numbered = "\n".join(f"{index}. {clause}" for index, clause in enumerate(clauses, 1))
    return [
        {"role": "system", "content": _STAGE1_SYSTEM},
        {
            "role": "user",
            "content": (
                f"원문 전체: {user_message}\n"
                f"번호 문장:\n{numbered}\n"
                f"검수된 접수 대상 A 근거: {product_index}. {target_clause}\n"
                f"접수 대상 A: {target_mention}\n"
                f"{_STAGE1_INSTRUCTION}"
            ),
        },
    ]


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate owner-resolution JSON key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise ValueError("nonfinite owner-resolution JSON value")


def _validated_span(item: object, clauses: tuple[str, ...]) -> dict | None:
    if item is None:
        return None
    if not isinstance(item, dict) or set(item) != {"clause_index", "quote"}:
        raise ValueError("source quote fields differ")
    index, quote = item["clause_index"], item["quote"]
    if type(index) is not int or type(quote) is not str:
        raise ValueError("source quote types differ")
    if (
        not 1 <= index <= len(clauses)
        or not quote.strip()
        or quote != quote.strip()
        or clauses[index - 1].count(quote) != 1
    ):
        raise ValueError("source quote is not uniquely anchored")
    start = clauses[index - 1].index(quote)
    return {
        "clause_index": index,
        "quote": quote,
        "start": start,
        "end": start + len(quote),
        "quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
    }


def validate_stage1(
    raw: str, user_message: str, *, product_index: int, target_mention: str
) -> dict:
    """Strictly parse source quotes; offsets count Unicode codepoints.

    An anchored C or cue is a model-supplied candidate, not verified ownership.
    """
    if not isinstance(raw, str):
        raise TypeError("stage-one response must be text")
    clauses = _clauses(user_message)
    _source_clause(clauses, product_index, target_mention)
    parsed = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    if not isinstance(parsed, dict) or set(parsed) != STAGE1_FIELDS:
        raise ValueError("stage-one response fields differ")
    kind = parsed["owner_kind"]
    cues = parsed["cue_spans"]
    distinct_index = parsed["distinct_cue_index"]
    if type(kind) is not str or kind not in OWNER_KINDS:
        raise ValueError("owner kind is unsupported")
    if not isinstance(cues, list) or len(cues) > 2:
        raise ValueError("cue spans must be a list of at most two quotes")
    if distinct_index is not None and (
        type(distinct_index) is not int or not 0 <= distinct_index < len(cues)
    ):
        raise ValueError("distinct cue index differs")
    event = _validated_span(parsed["event_span"], clauses)
    subject = _validated_span(parsed["subject_span"], clauses)
    owner = _validated_span(parsed["owner_span"], clauses)
    validated_cues = [_validated_span(item, clauses) for item in cues]
    if any(cue is None for cue in validated_cues):
        raise ValueError("cue quote cannot be null")
    if owner is None and (kind != "unresolved" or distinct_index is not None):
        raise ValueError("missing owner cannot claim a connection")
    if owner is not None and kind == "unresolved":
        raise ValueError("unresolved owner kind must omit owner span")
    if distinct_index is not None and kind != "explicit":
        raise ValueError("distinct cue requires an explicit owner")
    return {
        "event_span": event,
        "subject_span": subject,
        "owner_span": owner,
        "owner_kind": kind,
        "cue_spans": validated_cues,
        "distinct_cue_index": distinct_index,
    }


def owner_resolution_stage2_schema() -> dict:
    """Constrain the relation classifier to three finite choices."""
    return {
        "type": "object",
        "properties": {"source_relation": {"enum": sorted(RELATIONS)}},
        "required": ["source_relation"],
        "additionalProperties": False,
    }


def owner_resolution_stage2_messages(
    user_message: str, stage1: dict, *, product_index: int, target_mention: str
) -> list[dict[str, str]]:
    """Pass original text plus validated in-memory E/B/C/cues, never gold labels."""
    clauses = _clauses(user_message)
    _source_clause(clauses, product_index, target_mention)
    if any(stage1[key] is None for key in ("event_span", "subject_span", "owner_span")):
        raise ValueError("stage two requires E, B, and C; runner must skip")
    numbered = "\n".join(f"{index}. {clause}" for index, clause in enumerate(clauses, 1))

    def cited(span: dict) -> str:
        return f"{span['clause_index']}. {span['quote']}"

    cues = ", ".join(cited(cue) for cue in stage1["cue_spans"]) or "없음"
    return [
        {"role": "system", "content": _STAGE2_SYSTEM},
        {
            "role": "user",
            "content": (
                f"원문 전체: {user_message}\n번호 문장:\n{numbered}\n"
                f"접수 대상 A: {product_index}. {target_mention}\n"
                f"검증된 위험 사건 E: {cited(stage1['event_span'])}\n"
                f"검증된 위험 주체 B: {cited(stage1['subject_span'])}\n"
                f"검증된 소속 대상 후보 C: {cited(stage1['owner_span'])}\n"
                f"C 연결 종류 후보: {stage1['owner_kind']}\n"
                f"연결 단서 후보: {cues}\n"
                f"별도 개체 단서 후보 번호: {stage1['distinct_cue_index']}\n"
                "후보 인용이 원문에 존재한다는 사실만 검증됐고 의미상 소속 관계는 "
                "확정되지 않았습니다. A와 B의 관계를 current, other, unknown 중 하나로 "
                '판단하세요. JSON 객체 하나만 반환하세요: {"source_relation":"current|other|unknown"}.'
            ),
        },
    ]


def validate_stage2(raw: str, stage1: dict) -> dict[str, str]:
    """Keep raw model relation; conservatively gate the effective relation."""
    if not isinstance(raw, str):
        raise TypeError("stage-two response must be text")
    parsed = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    if not isinstance(parsed, dict) or set(parsed) != {"source_relation"}:
        raise ValueError("stage-two response fields differ")
    model_relation = parsed["source_relation"]
    if type(model_relation) is not str or model_relation not in RELATIONS:
        raise ValueError("stage-two relation is unsupported")
    if any(stage1[key] is None for key in ("event_span", "subject_span", "owner_span")):
        effective = "unknown"
    elif model_relation == "other" and not (
        stage1["owner_kind"] == "explicit" and stage1["distinct_cue_index"] is not None
    ):
        effective = "unknown"
    else:
        effective = model_relation
    return {"model_relation": model_relation, "effective_relation": effective}
