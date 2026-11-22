"""Annotate source candidates without deciding which one owns an event."""

from __future__ import annotations

from dataclasses import dataclass

from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v8.boundary_audit import candidate_views
from experiments.as_safety_v2.quotes import split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate


@dataclass(frozen=True)
class CandidateEvidence:
    candidate: SourceCandidate
    event_position: str
    nominal_chunk: bool


def annotate_candidates(
    message: str, event_span: dict, kiwi: Kiwi
) -> tuple[CandidateEvidence, ...]:
    """Describe positions and morphology only; never infer an E-to-B link."""
    clauses = split_clauses(message)
    index = event_span["clause_index"]
    quote = event_span["quote"]
    if (
        type(index) is not int
        or not 1 <= index <= len(clauses)
        or type(quote) is not str
        or not quote
        or clauses[index - 1].count(quote) != 1
    ):
        raise ValueError("event quote must be unique and anchored")
    start = clauses[index - 1].index(quote)
    end = start + len(quote)
    views = candidate_views(message, kiwi)
    chunk_ids = {item.id for item in views["nominal_chunk"]}
    result = []
    for candidate in views["nominal_end"]:
        if candidate.clause_index != index:
            position = "other_clause"
        elif candidate.end <= start:
            position = "before"
        elif candidate.start >= end:
            position = "after"
        elif candidate.start >= start and candidate.end <= end:
            position = "inside_event"
        else:
            position = "crosses_event"
        result.append(CandidateEvidence(candidate, position, candidate.id in chunk_ids))
    return tuple(result)
