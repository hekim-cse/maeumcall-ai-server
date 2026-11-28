"""Audit source selection over the full catalog on exposed ES development cases."""

import hashlib
import json
from collections import Counter
from importlib.metadata import version

from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_device_context import device_context_source
from experiments.as_safety_device_operation import device_operation_source
from experiments.as_safety_pair_evaluation import Detector, predict
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.source_lattice import (
    SourceCandidate,
    generate_source_lattice,
    source_candidate_status,
)
from scripts.audit_as_safety_source_lattice import CASES

INPUT_SHA256 = "49e4e960d901c037c7d10de6899aaeade3c71809060772571f0c8f58409d52f7"
MAX_WINDOW_TOKENS = 5
MAX_CANDIDATES = 192
DETECTORS = {"device_context": device_context_source, "device_operation": device_operation_source}


def approvals(
    detector: Detector,
    source: str,
    clauses: tuple[str, ...],
    event: dict,
    occurrence: str,
    candidates: tuple[SourceCandidate, ...],
    kiwi: Kiwi,
) -> tuple[list[str], int]:
    approved = []
    errors = 0
    for candidate in candidates:
        outcome = predict(detector, FixedPair(source, clauses, event, candidate), occurrence, kiwi)
        if outcome == "approve":
            approved.append(candidate.id)
        elif outcome == "error":
            errors += 1
    return approved, errors


def score(approved: list[str], errors: int, gold_id: str | None, availability: str) -> str:
    if errors:
        return "error"
    if len(approved) > 1:
        return "ambiguous"
    if approved:
        return "exact" if approved[0] == gold_id else "wrong_selection"
    return {
        "no_gold_owner": "correct_unresolved",
        "selected": "missed_available",
        "truncated": "unavailable_truncated",
        "not_generated": "unavailable_not_generated",
    }[availability]


def audit() -> dict:
    raw = CASES.read_bytes()
    if hashlib.sha256(raw).hexdigest() != INPUT_SHA256:
        raise ValueError("reviewed ES input changed")
    kiwi = Kiwi()
    rows = []
    skipped = []
    for case in json.loads(raw)["cases"]:
        source = case["user_message"]
        clauses = split_clauses(source)
        lattice = generate_source_lattice(
            source, max_window_tokens=MAX_WINDOW_TOKENS, max_candidates=MAX_CANDIDATES
        )
        candidates_by_span = {(c.clause_index, c.start, c.end): c.id for c in lattice.candidates}
        for index, reviewed in enumerate(case["events"], 1):
            identifier = f"{case['id']}-{index}"
            occurrence = reviewed["occurrence"]
            if occurrence == "nonoccurring":
                skipped.append(identifier)
                continue
            if occurrence not in {"observed", "uncertain"}:
                raise ValueError(f"unexpected occurrence in {identifier}")
            event = anchor_span(reviewed["event_span"], clauses, field=f"{identifier}.event")
            if event is None:
                raise ValueError(f"missing event in {identifier}")
            predictions = {
                name: approvals(
                    detector, source, clauses, event, occurrence, lattice.candidates, kiwi
                )
                for name, detector in DETECTORS.items()
            }
            gold = anchor_span(reviewed["hazard_owner_span"], clauses, field=f"{identifier}.owner")
            availability = "no_gold_owner"
            gold_id = None
            if gold is not None:
                position = {key: gold[key] for key in ("clause_index", "start", "end")}
                availability = source_candidate_status(lattice, **position)
                gold_id = candidates_by_span.get((gold["clause_index"], gold["start"], gold["end"]))
            rows.append(
                {
                    "event": identifier,
                    "occurrence": occurrence,
                    "offered_candidates": len(lattice.candidates),
                    "gold_availability": availability,
                    "gold_candidate": gold_id,
                    "rules": {
                        name: {
                            "approved_candidates": approved,
                            "candidate_errors": errors,
                            "outcome": score(approved, errors, gold_id, availability),
                        }
                        for name, (approved, errors) in predictions.items()
                    },
                }
            )
    return {
        "kind": "as_safety_source_selection_es_development_v1",
        "input_sha256": INPUT_SHA256,
        "kiwipiepy": version("kiwipiepy"),
        "kiwipiepy_model": version("kiwipiepy_model"),
        "candidate_settings": {
            "max_window_tokens": MAX_WINDOW_TOKENS,
            "max_candidates": MAX_CANDIDATES,
        },
        "skipped_nonoccurring": skipped,
        "gold_availability": dict(
            sorted(Counter(row["gold_availability"] for row in rows).items())
        ),
        "outcomes": {
            name: dict(sorted(Counter(row["rules"][name]["outcome"] for row in rows).items()))
            for name in DETECTORS
        },
        "rows": rows,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
