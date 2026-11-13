"""Bounded source-derived candidate IDs for A/S extraction comparison.

The generator sees only the utterance. Reviewed E/B/C spans are supplied
separately to ``measure_candidate_coverage`` after generation; they are never
used to construct prompts or candidate lists.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from experiments.as_safety_v2.extraction import OWNER_KINDS, _target_clause
from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.quotes import anchor_span, split_clauses

_EDGE_PUNCTUATION = " \t\n\r.,!?。！？;:()[]{}\"'“”‘’"
# Surface variants are source substrings, not normalized words or reviewed labels.
# Long suffixes precede short ones so that `충전기에서` can yield `충전기`.
_FINAL_PARTICLES = (
    "에서",
    "으로",
    "에게",
    "한테",
    "부터",
    "까지",
    "의",
    "을",
    "를",
    "이",
    "가",
    "은",
    "는",
    "에",
    "로",
)
_FIELDS = frozenset({"event_id", "subject_id", "owner_id", "owner_kind"})
_SOURCE_FIELDS = ("event_span", "subject_span", "owner_span")


@dataclass(frozen=True)
class Candidate:
    id: str
    clause_index: int
    quote: str
    start: int
    end: int
    quote_sha256: str


@dataclass(frozen=True)
class CandidateSet:
    source_sha256: str
    candidates: tuple[Candidate, ...]
    generated: tuple[Candidate, ...]

    @property
    def truncated(self) -> bool:
        return len(self.candidates) < len(self.generated)


def _source_hash(user_message: str) -> str:
    return hashlib.sha256(user_message.encode("utf-8")).hexdigest()


def _trim_edges(clause: str, start: int, end: int) -> tuple[int, int]:
    """Trim boundary punctuation and all Unicode whitespace, preserving the interior."""
    while start < end and (clause[start].isspace() or clause[start] in _EDGE_PUNCTUATION):
        start += 1
    while start < end and (clause[end - 1].isspace() or clause[end - 1] in _EDGE_PUNCTUATION):
        end -= 1
    return start, end


def _check_source(user_message: str, candidate_set: CandidateSet) -> tuple[str, ...]:
    clauses = split_clauses(user_message)
    if type(candidate_set) is not CandidateSet or candidate_set.source_sha256 != _source_hash(
        user_message
    ):
        raise ValidationError("candidate_source_invalid", "candidate_set")
    return clauses


def generate_candidates(
    user_message: str, *, max_window_tokens: int = 5, max_candidates: int = 192
) -> CandidateSet:
    """Enumerate source token windows and their particle-stripped substrings.

    Candidate order is shorter windows first, then source clause and position.
    No model output or reviewed label enters this function. The full generated
    set is retained only for offline coverage attribution when truncation occurs.
    """
    if type(max_window_tokens) is not int or not 1 <= max_window_tokens <= 8:
        raise ValueError("max_window_tokens must be 1..8")
    if type(max_candidates) is not int or not 1 <= max_candidates <= 256:
        raise ValueError("max_candidates must be 1..256")
    clauses = split_clauses(user_message)
    tokens = [tuple(re.finditer(r"\S+", clause)) for clause in clauses]
    generated: list[Candidate] = []
    seen: set[tuple[int, int, int]] = set()
    for width in range(1, max_window_tokens + 1):
        for clause_index, (clause, clause_tokens) in enumerate(
            zip(clauses, tokens, strict=True), 1
        ):
            for first in range(len(clause_tokens) - width + 1):
                start = clause_tokens[first].start()
                end = clause_tokens[first + width - 1].end()
                start, end = _trim_edges(clause, start, end)
                if start == end:
                    continue
                bare_end = end
                last_token = clause[clause_tokens[first + width - 1].start() : end]
                for particle in _FINAL_PARTICLES:
                    if last_token.endswith(particle) and len(last_token) - len(particle) >= 2:
                        bare_end = end - len(particle)
                        break
                for variant_end in (end, bare_end):
                    if (clause_index, start, variant_end) in seen:
                        continue
                    quote = clause[start:variant_end]
                    try:
                        anchored = anchor_span(
                            {"clause_index": clause_index, "quote": quote},
                            clauses,
                            field="candidate",
                        )
                    except ValidationError as error:
                        if error.code == "quote_nonunique":
                            continue
                        raise
                    seen.add((clause_index, start, variant_end))
                    generated.append(
                        Candidate(
                            id=f"P{len(generated) + 1:03}",
                            clause_index=clause_index,
                            quote=quote,
                            start=anchored["start"],
                            end=anchored["end"],
                            quote_sha256=anchored["quote_sha256"],
                        )
                    )
    return CandidateSet(
        source_sha256=_source_hash(user_message),
        candidates=tuple(generated[:max_candidates]),
        generated=tuple(generated),
    )


def measure_candidate_coverage(
    candidate_set: CandidateSet,
    reviewed_spans: Mapping[str, Sequence[dict]],
) -> dict:
    """Score source candidate recall offline; never call this in prompt building.

    Each field may have multiple reviewed acceptable spans. ``not_generated``
    means the window algorithm missed all of them; ``truncated`` means at least
    one existed but was excluded from the bounded model-facing list.
    """
    if set(reviewed_spans) != set(_SOURCE_FIELDS):
        raise ValueError("reviewed span fields differ")
    selected = {(item.clause_index, item.quote) for item in candidate_set.candidates}
    generated = {(item.clause_index, item.quote) for item in candidate_set.generated}
    by_field: dict[str, str] = {}
    by_span: dict[str, list[dict]] = {}
    for field in _SOURCE_FIELDS:
        accepted = reviewed_spans[field]
        if not accepted or any(
            type(span) is not dict
            or set(span) != {"clause_index", "quote"}
            or type(span["clause_index"]) is not int
            or type(span["quote"]) is not str
            for span in accepted
        ):
            raise ValueError(f"invalid reviewed spans: {field}")
        choices = {(span["clause_index"], span["quote"]) for span in accepted}
        by_span[field] = [
            {
                "clause_index": span["clause_index"],
                "quote_sha256": _source_hash(span["quote"]),
                "status": (
                    "selected"
                    if (span["clause_index"], span["quote"]) in selected
                    else "truncated"
                    if (span["clause_index"], span["quote"]) in generated
                    else "not_generated"
                ),
            }
            for span in accepted
        ]
        by_field[field] = (
            "selected"
            if choices & selected
            else "truncated"
            if choices & generated
            else "not_generated"
        )
    return {
        "denominator": len(_SOURCE_FIELDS),
        "selected_hits": sum(status == "selected" for status in by_field.values()),
        "generated_hits": sum(status != "not_generated" for status in by_field.values()),
        "truncated_hits": sum(status == "truncated" for status in by_field.values()),
        "by_field": by_field,
        "by_span": by_span,
        "candidate_count": len(candidate_set.candidates),
        "generated_count": len(candidate_set.generated),
        "truncated": candidate_set.truncated,
    }


def stage1_id_messages(
    user_message: str,
    candidate_set: CandidateSet,
    *,
    product_index: int,
    target_mention: str,
) -> list[dict[str, str]]:
    """Show source-derived IDs plus reviewed target A, never reviewed E/B/C."""
    clauses = _check_source(user_message, candidate_set)
    _target_clause(clauses, product_index, target_mention)
    numbered = "\n".join(f"{index}. {clause}" for index, clause in enumerate(clauses, 1))
    choices = "\n".join(
        f"{item.id} | {item.clause_index}번 | {item.quote}" for item in candidate_set.candidates
    )
    return [
        {
            "role": "system",
            "content": "A/S 위험 사건·위험 주체·소속 대상의 원문 후보 ID를 고릅니다.",
        },
        {
            "role": "user",
            "content": (
                f"원문 전체: {user_message}\n번호 문장:\n{numbered}\n"
                f"검수된 접수 대상 A: {product_index}. {target_mention}\n"
                f"원문에서 자동 생성한 후보 목록:\n{choices}\n"
                "위험 사건 E의 event_id, 물리적 위험 주체 B의 subject_id, "
                "B의 소속 물건 또는 지시어 선행사 C의 owner_id를 목록에서 고르세요. "
                "없으면 null로 두세요. owner_kind는 직접 명시된 C라면 explicit, "
                "앞 문장 제품이나 지시어 선행사를 연결했다면 implicit_coreference, "
                "C를 찾지 못하면 unresolved입니다. "
                "접수 대상 A의 일반 고장과 별도 제품의 위험 사건을 혼동하지 마세요. "
                "최종 관계는 판단하지 마세요. JSON 객체에는 event_id, subject_id, "
                "owner_id, owner_kind 네 키만 넣으세요."
            ),
        },
    ]


def stage1_id_schema(candidate_set: CandidateSet) -> dict:
    ids = [item.id for item in candidate_set.candidates]
    return {
        "type": "object",
        "properties": {
            "event_id": {"enum": [None, *ids]},
            "subject_id": {"enum": [None, *ids]},
            "owner_id": {"enum": [None, *ids]},
            "owner_kind": {"enum": sorted(OWNER_KINDS)},
        },
        "required": sorted(_FIELDS),
        "additionalProperties": False,
    }


def validate_stage1_ids(
    raw: str,
    user_message: str,
    candidate_set: CandidateSet,
    *,
    product_index: int,
    target_mention: str,
) -> dict:
    """Validate selected IDs against the bounded source-derived list."""
    clauses = _check_source(user_message, candidate_set)
    _target_clause(clauses, product_index, target_mention)
    parsed = parse_model_json(raw)
    if type(parsed) is not dict or set(parsed) != _FIELDS:
        raise ValidationError("fields_invalid", "stage1_ids")
    kind = parsed["owner_kind"]
    if type(kind) is not str or kind not in OWNER_KINDS:
        raise ValidationError("owner_kind_invalid", "owner_kind")
    indexed = {item.id: item for item in candidate_set.candidates}
    selected_ids = {}
    extraction = {}
    for id_field, span_field in (
        ("event_id", "event_span"),
        ("subject_id", "subject_span"),
        ("owner_id", "owner_span"),
    ):
        selected_id = parsed[id_field]
        if selected_id is not None and (type(selected_id) is not str or selected_id not in indexed):
            raise ValidationError("candidate_id_invalid", id_field)
        selected_ids[id_field] = selected_id
        item = indexed.get(selected_id)
        if item is None:
            extraction[span_field] = None
            continue
        anchored = anchor_span(
            {"clause_index": item.clause_index, "quote": item.quote},
            clauses,
            field=span_field,
        )
        if (
            anchored["start"] != item.start
            or anchored["end"] != item.end
            or anchored["quote_sha256"] != item.quote_sha256
        ):
            raise ValidationError("candidate_integrity_invalid", id_field)
        extraction[span_field] = anchored
    if (extraction["owner_span"] is None) != (kind == "unresolved"):
        raise ValidationError("owner_consistency_invalid", "owner_id")
    extraction["owner_kind"] = kind
    return {"extraction": extraction, "selected_ids": selected_ids}
