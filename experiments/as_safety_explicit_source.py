"""Offline baseline for a direct Korean locative attachment to an observed event."""

from collections.abc import Callable
from dataclasses import dataclass

from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair

SOURCE_MARKERS = {"에서", "로부터", "으로부터"}
NOUN_TAGS = {"NNG", "NNP"}


@dataclass(frozen=True)
class DirectSource:
    clause_index: int
    source_start: int
    source_end: int
    event_start: int
    event_end: int


def explicit_source(
    pair: FixedPair,
    occurrence: str,
    kiwi: Kiwi,
    *,
    nominal_evidence: Callable[[str], bool] | None = None,
) -> DirectSource | None:
    """Accept only a whole nominal phrase directly attached to the anchored event."""
    event = pair.event
    candidate = pair.candidate
    index = event["clause_index"]
    clause = pair.clauses[index - 1]
    start, end = event["start"], event["end"]
    if clause[start:end] != event["quote"]:
        raise ValueError("event anchor differs from the source")
    candidate_clause = pair.clauses[candidate.clause_index - 1]
    if candidate_clause[candidate.start : candidate.end] != candidate.quote:
        raise ValueError("candidate anchor differs from the source")

    if occurrence != "observed" or candidate.clause_index != index:
        return None
    if candidate.start != 0 or not 0 < candidate.end < start:
        return None
    gap = clause[candidate.end : start]
    if not gap.endswith(" ") or gap.rstrip(" ") not in SOURCE_MARKERS:
        return None
    if clause[end:] not in {"", ".", "。"}:
        return None
    if nominal_evidence is None or not nominal_evidence(candidate.quote):
        tokens = kiwi.tokenize(candidate.quote)
        if not tokens or any(token.tag not in NOUN_TAGS for token in tokens):
            return None
    return DirectSource(index, candidate.start, candidate.end, start, end)
