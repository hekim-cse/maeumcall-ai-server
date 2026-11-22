"""Replay the exposed PC/NC failure as an offline candidate inventory."""

from __future__ import annotations

import hashlib
import json

from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v8 import boundary_audit as v8
from experiments.as_safety_atomic_edges_v10 import probe
from experiments.as_safety_atomic_edges_v11.evidence_view import annotate_candidates


def audit() -> dict:
    cases = probe.cases()
    previous = v8.audit()
    kiwi = Kiwi()
    rows = []
    for name in probe.CASE_ORDER:
        case = cases[name]
        annotations = annotate_candidates(case["user_message"], case["event_span"], kiwi)
        gold = case["gold_subject_span"]
        rows.append(
            {
                "case_id": name,
                "source_sha256": hashlib.sha256(case["user_message"].encode()).hexdigest(),
                "candidate_count": len(annotations),
                "position_counts": {
                    position: sum(item.event_position == position for item in annotations)
                    for position in (
                        "other_clause",
                        "before",
                        "inside_event",
                        "crosses_event",
                        "after",
                    )
                },
                "nominal_chunk_count": sum(item.nominal_chunk for item in annotations),
                "gold_present_before_event": (
                    any(
                        item.event_position == "before"
                        and item.candidate.clause_index == gold["clause_index"]
                        and item.candidate.quote == gold["quote"]
                        for item in annotations
                    )
                    if gold is not None
                    else None
                ),
                "candidate_ids_by_position": {
                    position: [
                        item.candidate.id for item in annotations if item.event_position == position
                    ]
                    for position in (
                        "other_clause",
                        "before",
                        "inside_event",
                        "crosses_event",
                        "after",
                    )
                },
            }
        )
    return {
        "kind": "as_safety_eb_candidate_evidence_v11_offline_audit",
        "model_called": False,
        "candidate_generation_source_only": True,
        "event_span_is_reviewed_input": True,
        "owner_or_abstention_inferred": False,
        "exposed_control_rows": rows,
        "previous_26_case_nominal_filter": {
            "case_count": previous["summary"]["case_count"],
            "positive_case_count": previous["summary"]["positive_case_count"],
            "null_case_count": previous["summary"]["null_case_count"],
            "nominal_end_candidates": previous["summary"]["candidate_count_by_filter"][
                "nominal_end"
            ],
            "nominal_chunk_candidates": previous["summary"]["candidate_count_by_filter"][
                "nominal_chunk"
            ],
            "nominal_end_gold_covered": previous["summary"]["positive_gold_covered_by_filter"][
                "nominal_end"
            ],
            "nominal_chunk_gold_covered": previous["summary"]["positive_gold_covered_by_filter"][
                "nominal_chunk"
            ],
            "nominal_chunk_gold_loss_ids": previous["summary"][
                "additional_gold_loss_case_ids_by_filter"
            ]["nominal_chunk"],
        },
    }


def main() -> None:
    print(json.dumps(audit(), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
