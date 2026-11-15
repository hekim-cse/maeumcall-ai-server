"""Compile the human-reviewed ES graph table into a frozen label input.

The default output remains a draft. Explicit approval status is only used
after the user has reviewed the table; this script cannot grant approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from experiments.as_safety_v2.evidence_graph import (
    ATTACHMENT_KINDS,
    EDGE_KINDS,
    validate_evidence_graph,
)
from experiments.as_safety_v4.cases import load_cases

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "docs/portfolio/nlu_safety_evidence_graph_v1_field_review.md"
DATASET = (
    ROOT
    / "evals/structured_nlu/data/ai_heldout"
    / "as-safety-event-source-v4-exploration-reviewed.v1.json"
)
ROW_ID = re.compile(r"ES\d{2}(?:-[12])?\Z")


def _edge_cell(cell: str, allowed: frozenset[str]) -> tuple[str, dict | None]:
    quoted = re.findall(r"`([^`]*)`", cell)
    if len(quoted) != 2 or quoted[0] not in allowed:
        raise ValueError("graph review cell differs")
    kind, quote = quoted
    if quote == "null":
        if kind != "unresolved":
            raise ValueError("resolved graph review cell cannot be null")
        return kind, None
    match = re.search(r"·\s*(\d+)\s+`([^`]+)`\s*\Z", cell)
    if match is None or match[2] != quote:
        raise ValueError("graph review evidence differs")
    return kind, {"clause_index": int(match[1]), "quote": quote}


def compile_labels(*, approved: bool = False, review_path: Path = REVIEW) -> dict:
    """Parse all proposed rows, then validate against existing reviewed ES data."""
    raw = review_path.read_bytes()
    rows: dict[tuple[str, int], dict] = {}
    for line in raw.decode("utf-8").splitlines():
        if not line.startswith("| ES"):
            continue
        columns = [column.strip() for column in line.strip("|").split("|")]
        if len(columns) != 5 or ROW_ID.fullmatch(columns[0]) is None:
            raise ValueError("graph review row differs")
        case_id, _, attachment_cell, edge_cell, _ = columns
        case_id, _, suffix = case_id.partition("-")
        index = int(suffix) if suffix else 1
        key = (case_id, index)
        if key in rows:
            raise ValueError("duplicate graph review row")
        attachment, attachment_span = _edge_cell(attachment_cell, ATTACHMENT_KINDS)
        edge, edge_span = _edge_cell(edge_cell, EDGE_KINDS)
        rows[key] = {
            "event_index": index,
            "event_subject_kind": attachment,
            "event_subject_evidence_span": attachment_span,
            "target_edge_kind": edge,
            "target_edge_evidence_span": edge_span,
        }
    cases = load_cases(DATASET)
    labels: list[dict] = []
    used: set[tuple[str, int]] = set()
    for case in cases:
        events: list[dict] = []
        for index, event in enumerate(case["events"], 1):
            key = (case["id"], index)
            if event["occurrence"] == "nonoccurring":
                if key in rows:
                    raise ValueError("nonoccurring event has a graph review row")
                events.append(
                    {
                        "event_index": index,
                        "event_subject_kind": None,
                        "event_subject_evidence_span": None,
                        "target_edge_kind": None,
                        "target_edge_evidence_span": None,
                    }
                )
                continue
            if key not in rows:
                raise ValueError(f"missing graph review row: {key}")
            label = rows[key]
            used.add(key)
            predicted = validate_evidence_graph(
                json.dumps(
                    {
                        "subject_span": event["hazard_owner_span"],
                        **{field: label[field] for field in label if field != "event_index"},
                    },
                    ensure_ascii=False,
                ),
                case["user_message"],
                event["event_span"],
                event["occurrence"],
                product_index=case["target"]["clause_index"],
                target_mention=case["target"]["quote"],
            )
            if predicted["effective_relation"] != event["owner_to_target"]:
                raise ValueError(f"graph review relation differs: {key}")
            events.append(label)
        labels.append({"id": case["id"], "events": events})
    if len(used) != 19 or used != set(rows):
        raise ValueError("graph review event count differs")
    return {
        "kind": "as_safety_evidence_graph_v1_labels",
        "review_status": (
            "owner_approved_for_exploratory_evaluation" if approved else "draft_pending_user_review"
        ),
        "review_sha256": hashlib.sha256(raw).hexdigest(),
        "cases": labels,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = compile_labels(approved=args.approved)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
