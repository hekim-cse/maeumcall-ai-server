"""Minimal E/B/C source extraction for the next A/S development experiment.

Only a reviewed service target A is supplied. Exact quote validation proves
that model-selected evidence exists in the utterance, not that it is the
semantically correct hazard event, subject, or owner.
"""

from __future__ import annotations

from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.quotes import anchor_span, split_clauses

FIELDS = frozenset({"event_span", "subject_span", "owner_span", "owner_kind"})
OWNER_KINDS = frozenset({"explicit", "implicit_coreference", "unresolved"})

_SYSTEM = (
    "A/S 접수 발화에서 위험 사건 E, 그 위험의 물리적 주체 B, "
    "B가 속한 대상 또는 지시어의 선행사 C를 찾는 추출기입니다. "
    "원문에 없는 표현을 만들지 마세요."
)
_INSTRUCTION = (
    "번호 문장에서 위험 사건 E, 위험 주체 B, B의 소속 대상 C를 각각 찾으세요. "
    "현재 접수 대상 A의 고장 사실이 별도 제품의 위험 사건보다 앞에 있어도, "
    "위험 사건이 명시된 문장을 먼저 고르세요. "
    "각 span은 해당 문장에서 실제로 연속해 나타나는 짧은 구절을 그대로 인용하고 "
    "1부터 시작하는 문장 번호를 붙이세요. 없는 구절은 null로 두세요. "
    "owner_kind는 C가 직접 명시된 경우 explicit, 앞 문장 제품이나 지시어의 "
    "선행사를 연결한 경우 implicit_coreference, C를 찾을 수 없는 경우 unresolved입니다. "
    "최종 current/other 관계나 안전 경로는 결정하지 마세요. "
    "JSON 객체의 필수 키는 event_span, subject_span, owner_span, owner_kind입니다. "
    "각 span은 clause_index 정수와 quote 문자열을 가진 객체 또는 null입니다. "
    "owner_kind는 explicit, implicit_coreference, unresolved 중 하나입니다. "
    "JSON 객체 하나만 반환하세요."
)


def _target_clause(clauses: tuple[str, ...], product_index: int, target_mention: str) -> str:
    if type(product_index) is not int or not 1 <= product_index <= len(clauses):
        raise ValidationError("target_invalid", "product_index")
    if (
        type(target_mention) is not str
        or not target_mention.strip()
        or target_mention != target_mention.strip()
        or clauses[product_index - 1].count(target_mention) != 1
    ):
        raise ValidationError("target_unanchored", "target_mention")
    return clauses[product_index - 1]


def stage1_messages(
    user_message: str, *, product_index: int, target_mention: str
) -> list[dict[str, str]]:
    """Supply the utterance and reviewed A, never the reviewed E/B/C or relation."""
    clauses = split_clauses(user_message)
    target_clause = _target_clause(clauses, product_index, target_mention)
    numbered = "\n".join(f"{index}. {clause}" for index, clause in enumerate(clauses, 1))
    return [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": (
                f"원문 전체: {user_message}\n"
                f"번호 문장:\n{numbered}\n"
                f"검수된 접수 대상 A: {product_index}. {target_mention}\n"
                f"A의 원문 문장: {target_clause}\n"
                f"{_INSTRUCTION}"
            ),
        },
    ]


def stage1_schema(user_message: str) -> dict:
    """Constrain field names, nullable spans and source clause IDs."""
    clauses = split_clauses(user_message)
    quote = {
        "type": "object",
        "properties": {
            "clause_index": {"enum": list(range(1, len(clauses) + 1))},
            "quote": {"type": "string", "minLength": 1, "maxLength": max(map(len, clauses))},
        },
        "required": ["clause_index", "quote"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            field: {"anyOf": [quote, {"type": "null"}]}
            for field in ("event_span", "subject_span", "owner_span")
        }
        | {"owner_kind": {"enum": sorted(OWNER_KINDS)}},
        "required": sorted(FIELDS),
        "additionalProperties": False,
    }


def validate_stage1(
    raw: str, user_message: str, *, product_index: int, target_mention: str
) -> dict:
    """Parse and anchor Stage1 output with finite, field-specific failures."""
    clauses = split_clauses(user_message)
    _target_clause(clauses, product_index, target_mention)
    parsed = parse_model_json(raw)
    if type(parsed) is not dict or set(parsed) != FIELDS:
        raise ValidationError("fields_invalid", "stage1")
    kind = parsed["owner_kind"]
    if type(kind) is not str or kind not in OWNER_KINDS:
        raise ValidationError("owner_kind_invalid", "owner_kind")
    spans = {
        field: anchor_span(parsed[field], clauses, field=field)
        for field in ("event_span", "subject_span", "owner_span")
    }
    if (spans["owner_span"] is None) != (kind == "unresolved"):
        raise ValidationError("owner_consistency_invalid", "owner_span")
    return spans | {"owner_kind": kind}
