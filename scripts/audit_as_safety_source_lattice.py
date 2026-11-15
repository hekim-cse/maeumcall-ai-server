"""Offline source-candidate coverage audit on exposed ES development examples.

Reviewed spans are read only after candidates have been generated from the
utterance. This reports exact span availability, not model selection quality.
"""

from __future__ import annotations

import json
from pathlib import Path

from experiments.as_safety_v2.quotes import split_clauses
from experiments.as_safety_v2.source_lattice import (
    generate_source_lattice,
    source_candidate_status,
)

ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ROOT
    / "evals/structured_nlu/data/ai_heldout"
    / "as-safety-event-source-v4-exploration-reviewed.v1.json"
)


def audit() -> dict:
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    rows: list[dict] = []
    for case in cases:
        utterance = case["user_message"]
        lattice = generate_source_lattice(utterance)
        clauses = split_clauses(utterance)
        for event_index, event in enumerate(case["events"], 1):
            reviewed = event["hazard_owner_span"]
            if reviewed is None:
                continue
            clause_index = reviewed["clause_index"]
            quote = reviewed["quote"]
            clause = clauses[clause_index - 1]
            if clause.count(quote) != 1:
                raise ValueError(f"ambiguous reviewed owner: {case['id']} event {event_index}")
            start = clause.index(quote)
            rows.append(
                {
                    "case_id": case["id"],
                    "event_index": event_index,
                    "status": source_candidate_status(
                        lattice,
                        clause_index=clause_index,
                        start=start,
                        end=start + len(quote),
                    ),
                    "selected_candidates": len(lattice.candidates),
                    "generated_candidates": len(lattice.generated),
                }
            )
    return {
        "kind": "as_safety_source_lattice_coverage_development_v1",
        "dataset": CASES.relative_to(ROOT).as_posix(),
        "denominator": len(rows),
        "selected": sum(row["status"] == "selected" for row in rows),
        "truncated": sum(row["status"] == "truncated" for row in rows),
        "not_generated": sum(row["status"] == "not_generated" for row in rows),
        "rows": rows,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
