"""Select numbered source sentences or abstain for each evidence role."""

import json

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_atomic_edges_v17 import evidence_contract
from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json

QUESTIONS = evidence_contract.QUESTIONS


def candidates(pair: FixedPair) -> dict[int, str]:
    """Keep the complete source, including distractors, in original order."""
    return dict(enumerate(pair.clauses, 1))


def messages(pair: FixedPair, *, reverse_questions: bool = False) -> list[dict[str, str]]:
    numbered = "\n".join(f"{index}. {text}" for index, text in candidates(pair).items())
    questions = QUESTIONS[::-1] if reverse_questions else QUESTIONS
    prompts = "\n".join(f"{key}: {question}" for key, question in questions)
    return [
        {"role": "system", "content": "위험 사건과 후보 구절의 관계에 대한 원문 근거를 고르세요."},
        {
            "role": "user",
            "content": (
                f"번호가 붙은 원문 근거 후보:\n{numbered}\n"
                f"위험 사건 E: {pair.event['clause_index']}번 | {pair.event['quote']}\n"
                f"후보 B: {pair.candidate.id} | {pair.candidate.clause_index}번 | "
                f"{pair.candidate.quote}\n"
                "각 질문에 근거가 있으면 번호 하나를 정수로 반환하세요. 근거가 없으면 "
                "null로 두세요. 후보가 등장한다는 이유만으로 출처를 확정하거나, "
                "출처가 불명확하다는 이유만으로 후보를 배제하지 마세요.\n"
                f"{prompts}\n세 키를 모두 포함한 JSON 객체만 반환하세요."
            ),
        },
    ]


def schema(pair: FixedPair) -> dict:
    keys = [key for key, _ in QUESTIONS]
    return {
        "type": "object",
        "properties": {key: {"enum": [*candidates(pair), None]} for key in keys},
        "required": keys,
        "additionalProperties": False,
    }


def validate_response(raw: str, pair: FixedPair) -> dict:
    parsed = parse_model_json(raw)
    if type(parsed) is not dict or set(parsed) != {key for key, _ in QUESTIONS}:
        raise ValidationError("fields_invalid", "candidate_evidence")
    offered = candidates(pair)
    spans = {}
    for key, index in parsed.items():
        if index is None:
            spans[key] = None
        elif type(index) is int and index in offered:
            spans[key] = {"clause_index": index, "quote": offered[index]}
        else:
            raise ValidationError("evidence_candidate_not_offered", key)
    return evidence_contract.validate_response(json.dumps(spans, ensure_ascii=False), pair)


def score(pair: FixedPair, gold: dict, result: dict | None) -> dict:
    """Measure coverage before scoring selection among covered answers."""
    expected = gold["evidence_clause_index"]
    covered = expected is not None and expected in candidates(pair)
    selected = None if result is None else result["evidence_clause_index"]
    return {
        "gold_candidate_offered": covered,
        "gold_evidence_selected_if_offered": (
            result is not None and selected == expected if covered else None
        ),
        "status_match": result is not None and result["relation_status"] == gold["relation_status"],
        "selected_evidence_candidate": selected,
    }
