"""Resolve a model-selected source candidate ID without accepting free quotes.

This module validates provenance and field consistency. It cannot establish
whether the selected candidate is the true event subject or belongs to A.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256

import kiwipiepy
from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v8.boundary_audit import KIWI_VERSION, candidate_views
from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.quotes import split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate, generate_source_lattice

_ID = re.compile(r"P[0-9]{3}\Z")
_KINDS = ("implicit", "location", "subject", "unresolved")
_RESOLVED = frozenset(_KINDS) - {"unresolved"}
_FIELDS = frozenset({"candidate_id", "event_subject_kind"})


@dataclass(frozen=True)
class CandidateCatalog:
    """A source-only selection set with stable IDs and checked offsets."""

    source: str
    candidates: tuple[SourceCandidate, ...]

    def __post_init__(self) -> None:
        if type(self.source) is not str:
            raise ValueError("source invalid")
        clauses = split_clauses(self.source)
        if not self.candidates:
            raise ValueError("candidate catalog is empty")
        seen_ids: set[str] = set()
        seen_positions: set[tuple[int, int, int]] = set()
        for item in self.candidates:
            if type(item.id) is not str or not _ID.fullmatch(item.id) or item.id in seen_ids:
                raise ValueError("candidate ID invalid or repeated")
            if type(item.clause_index) is not int or not 1 <= item.clause_index <= len(clauses):
                raise ValueError("candidate clause invalid")
            clause = clauses[item.clause_index - 1]
            if (
                type(item.start) is not int
                or type(item.end) is not int
                or not 0 <= item.start < item.end <= len(clause)
                or clause[item.start : item.end] != item.quote
                or sha256(item.quote.encode("utf-8")).hexdigest() != item.quote_sha256
            ):
                raise ValueError("candidate source span invalid")
            position = (item.clause_index, item.start, item.end)
            if position in seen_positions:
                raise ValueError("candidate position repeated")
            seen_ids.add(item.id)
            seen_positions.add(position)

    def schema(self) -> dict:
        """Constrain the wire output to one listed ID or an explicit hold."""
        return {
            "type": "object",
            "properties": {
                "candidate_id": {
                    "anyOf": [{"enum": [c.id for c in self.candidates]}, {"type": "null"}]
                },
                "event_subject_kind": {"enum": list(_KINDS)},
            },
            "required": sorted(_FIELDS),
            "additionalProperties": False,
        }

    def resolve(self, raw: str) -> dict:
        """Reject invented IDs and incompatible holds before span materialization."""
        parsed = parse_model_json(raw)
        if type(parsed) is not dict or set(parsed) != _FIELDS:
            raise ValidationError("fields_invalid", "candidate_selection")
        candidate_id = parsed["candidate_id"]
        kind = parsed["event_subject_kind"]
        if type(kind) is not str or kind not in _KINDS:
            raise ValidationError("subject_kind_invalid", "event_subject_kind")
        if candidate_id is None:
            if kind != "unresolved":
                raise ValidationError("selection_consistency_invalid", "candidate_id")
            return {"candidate_id": None, "subject_span": None, "event_subject_kind": kind}
        if type(candidate_id) is not str or not candidate_id:
            raise ValidationError("candidate_id_invalid", "candidate_id")
        candidate = next((c for c in self.candidates if c.id == candidate_id), None)
        if candidate is None:
            raise ValidationError("candidate_not_offered", "candidate_id")
        if kind not in _RESOLVED:
            raise ValidationError("selection_consistency_invalid", "event_subject_kind")
        return {
            "candidate_id": candidate_id,
            "subject_span": {"clause_index": candidate.clause_index, "quote": candidate.quote},
            "event_subject_kind": kind,
        }


def catalog_from_candidates(source: str, candidates: Sequence[SourceCandidate]) -> CandidateCatalog:
    """Accept a candidate set only after source-only generation elsewhere."""
    return CandidateCatalog(source=source, candidates=tuple(candidates))


def nominal_catalog(source: str, kiwi: Kiwi) -> CandidateCatalog:
    """Produce the v8 nominal subset using only the utterance text."""
    if kiwipiepy.__version__ != KIWI_VERSION:
        raise ValueError("Kiwi version differs")
    lattice = generate_source_lattice(source, max_window_tokens=5, max_candidates=192)
    if lattice.truncated:
        raise ValueError("source candidate list truncated")
    selected = candidate_views(source, kiwi)["nominal_end"]
    return catalog_from_candidates(source, selected)
