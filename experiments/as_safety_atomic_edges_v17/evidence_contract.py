"""Extract source evidence before deriving a fixed-pair relation status."""

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.quotes import anchor_span

QUESTIONS = (
    (
        "source_evidence",
        "이 후보가 바로 이 사건의 물리적 출처임을 보여 주는 원문 구절이 있나요?",
    ),
    (
        "exclusion_evidence",
        "후보가 출처가 아니라 현상 자체·잘못된 구절이거나, 원문이 이 후보를 출처에서 배제하나요?",
    ),
    (
        "uncertainty_evidence",
        "이 사건의 출처를 확인할 수 없다고 원문에서 명시하나요?",
    ),
)


def messages(pair: FixedPair, *, reverse_questions: bool = False) -> list[dict[str, str]]:
    numbered = "\n".join(f"{index}. {clause}" for index, clause in enumerate(pair.clauses, 1))
    questions = reversed(QUESTIONS) if reverse_questions else iter(QUESTIONS)
    prompts = "\n".join(f"{key}: {question}" for key, question in questions)
    return [
        {
            "role": "system",
            "content": "위험 사건과 후보 구절의 관계를 판단할 수 있는 원문 근거만 추출하세요.",
        },
        {
            "role": "user",
            "content": (
                f"번호 문장:\n{numbered}\n"
                f"위험 사건 E: {pair.event['clause_index']}번 | {pair.event['quote']}\n"
                f"후보 B: {pair.candidate.id} | {pair.candidate.clause_index}번 | "
                f"{pair.candidate.quote}\n"
                "세 질문을 각각 확인하세요. 근거가 있는 질문에는 한 문장에서 연속하는 "
                "원문 구절과 문장 번호를 quote와 clause_index에 적으세요. "
                "근거가 없으면 해당 값을 null로 두세요. 후보 구절이 등장한다는 사실만으로 "
                "출처를 확정하거나, 출처가 불명확하다는 이유만으로 후보를 배제하지 마세요.\n"
                f"{prompts}\n세 키를 모두 포함한 JSON 객체만 반환하세요."
            ),
        },
    ]


def schema(pair: FixedPair) -> dict:
    span = {
        "type": "object",
        "properties": {
            "clause_index": {"enum": list(range(1, len(pair.clauses) + 1))},
            "quote": {"type": "string", "minLength": 1},
        },
        "required": ["clause_index", "quote"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {key: {"anyOf": [span, {"type": "null"}]} for key, _ in QUESTIONS},
        "required": [key for key, _ in QUESTIONS],
        "additionalProperties": False,
    }


def validate_response(raw: str, pair: FixedPair) -> dict:
    parsed = parse_model_json(raw)
    if type(parsed) is not dict or set(parsed) != {key for key, _ in QUESTIONS}:
        raise ValidationError("fields_invalid", "candidate_evidence")
    evidence = {key: anchor_span(parsed[key], pair.clauses, field=key) for key, _ in QUESTIONS}
    source = evidence["source_evidence"]
    exclusion = evidence["exclusion_evidence"]
    uncertainty = evidence["uncertainty_evidence"]
    if source is not None and (exclusion is not None or uncertainty is not None):
        raise ValidationError("conflicting_source_evidence", "candidate_evidence")

    if source is not None:
        status, decisive = "supported", source
    elif exclusion is not None:
        status, decisive = "unsupported", exclusion
    else:
        status, decisive = "insufficient", uncertainty
    return {
        "candidate_id": pair.candidate.id,
        "relation_status": status,
        "evidence_clause_index": decisive["clause_index"] if decisive is not None else None,
        "evidence": evidence,
    }
