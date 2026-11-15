"""Development-only, source-derived span lattice for A/S relation experiments.

Candidates identify text positions; they do not identify hazards, products, or
relations. Reviewed labels must be compared only after generation. In
particular, an anchored candidate is not evidence that an entity link is true.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from experiments.as_safety_v2.quotes import split_clauses

_EDGE_PUNCTUATION = ".,!?。！？;:()[]{}\"'“”‘’"
# Longer combined postpositions must precede their shorter suffixes. These
# produce alternative *source substrings*, not morphological analyses.
_POSTPOSITIONS = (
    "에게서는",
    "한테서는",
    "으로서는",
    "에서는",
    "에게서",
    "한테서",
    "으로서",
    "에서",
    "으로",
    "에게",
    "한테",
    "부터",
    "까지",
    "와는",
    "과는",
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


@dataclass(frozen=True)
class SourceCandidate:
    id: str
    clause_index: int
    start: int
    end: int
    quote: str
    quote_sha256: str


@dataclass(frozen=True)
class SourceLattice:
    source_sha256: str
    candidates: tuple[SourceCandidate, ...]
    generated: tuple[SourceCandidate, ...]

    @property
    def truncated(self) -> bool:
        return len(self.candidates) < len(self.generated)


def _trim(clause: str, start: int, end: int) -> tuple[int, int]:
    while start < end and (clause[start].isspace() or clause[start] in _EDGE_PUNCTUATION):
        start += 1
    while start < end and (clause[end - 1].isspace() or clause[end - 1] in _EDGE_PUNCTUATION):
        end -= 1
    return start, end


def _bare_end(clause: str, token_start: int, end: int) -> int | None:
    token = clause[token_start:end]
    for suffix in _POSTPOSITIONS:
        # A one-character source stem, e.g. `뒤` in `뒤에서`, is legitimate.
        # The string is still just a candidate; no wordhood is asserted.
        if token.endswith(suffix) and len(token) > len(suffix):
            return end - len(suffix)
    return None


def generate_source_lattice(
    user_message: str, *, max_window_tokens: int = 5, max_candidates: int = 192
) -> SourceLattice:
    """Enumerate exact token windows and possible postposition-free endings.

    The bounded list is for a later model experiment. ``generated`` retains
    all positions so offline analysis can distinguish generation misses from
    truncation. IDs are stable for the same source and settings.
    """
    if type(max_window_tokens) is not int or not 1 <= max_window_tokens <= 8:
        raise ValueError("max_window_tokens must be 1..8")
    if type(max_candidates) is not int or not 1 <= max_candidates <= 256:
        raise ValueError("max_candidates must be 1..256")
    clauses = split_clauses(user_message)
    tokens = tuple(tuple(re.finditer(r"\S+", clause)) for clause in clauses)
    generated: list[SourceCandidate] = []
    seen: set[tuple[int, int, int]] = set()
    for width in range(1, max_window_tokens + 1):
        for clause_index, (clause, clause_tokens) in enumerate(zip(clauses, tokens, strict=True), 1):
            for first in range(len(clause_tokens) - width + 1):
                start, end = _trim(
                    clause,
                    clause_tokens[first].start(),
                    clause_tokens[first + width - 1].end(),
                )
                if start == end:
                    continue
                token_start = clause_tokens[first + width - 1].start()
                bare_end = _bare_end(clause, token_start, end)
                for variant_end in (end, bare_end):
                    if variant_end is None or variant_end <= start:
                        continue
                    key = (clause_index, start, variant_end)
                    if key in seen:
                        continue
                    seen.add(key)
                    quote = clause[start:variant_end]
                    generated.append(
                        SourceCandidate(
                            id=f"P{len(generated) + 1:03}",
                            clause_index=clause_index,
                            start=start,
                            end=variant_end,
                            quote=quote,
                            quote_sha256=hashlib.sha256(quote.encode("utf-8")).hexdigest(),
                        )
                    )
    return SourceLattice(
        source_sha256=hashlib.sha256(user_message.encode("utf-8")).hexdigest(),
        candidates=tuple(generated[:max_candidates]),
        generated=tuple(generated),
    )


def source_candidate_status(
    lattice: SourceLattice, *, clause_index: int, start: int, end: int
) -> str:
    """Offline exact-offset coverage. Never feed reviewed offsets into generation."""
    key = (clause_index, start, end)
    if any((c.clause_index, c.start, c.end) == key for c in lattice.candidates):
        return "selected"
    if any((c.clause_index, c.start, c.end) == key for c in lattice.generated):
        return "truncated"
    return "not_generated"
