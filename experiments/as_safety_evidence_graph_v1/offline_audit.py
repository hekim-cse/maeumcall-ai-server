"""Posthoc, read-only error decomposition of the frozen ES graph responses.

This is an exposed development-set diagnosis, not a rerun or new model score.
It verifies the public journal and private bytes before reading responses, then
audits all fields independently of the original first-error contract result.
Only finite codes, booleans, identifiers and hashes leave the private machine.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from experiments.as_safety_evidence_graph_v1 import verify as frozen
from experiments.as_safety_v4.cases import load_cases

SPAN_FIELDS = (
    "subject_span",
    "event_subject_evidence_span",
    "target_edge_evidence_span",
)
KIND_FIELDS = ("event_subject_kind", "target_edge_kind")
ANCHOR_CODES = frozenset(
    {
        "anchored",
        "null",
        "wrong_clause_unique",
        "wrong_clause_ambiguous",
        "quote_absent",
        "quote_nonunique",
        "quote_fields_invalid",
        "quote_index_invalid",
        "quote_type_invalid",
        "quote_blank",
    }
)
RELATIONS = {
    "same_entity": "current",
    "part_of": "current",
    "located_at": "current",
    "coreference": "current",
    "distinct": "other",
    "unresolved": "unknown",
}


def _anchor_status(
    value: object, clauses: tuple[str, ...], field: str
) -> tuple[str, dict | None, int | None]:
    """Classify one quote without hiding later fields behind an early failure."""
    if value is None:
        return "null", None, None
    try:
        return "anchored", frozen._span(value, clauses, field), None
    except frozen.ContractError as error:
        if error.code == "quote_unanchored" and type(value) is dict:
            quote = value.get("quote")
            if type(quote) is str:
                matches = []
                for index, clause in enumerate(clauses, 1):
                    start = clause.find(quote)
                    while start >= 0:
                        matches.append(index)
                        start = clause.find(quote, start + 1)
                if len(matches) == 1:
                    return "wrong_clause_unique", None, matches[0]
                if matches:
                    return "wrong_clause_ambiguous", None, None
                return "quote_absent", None, None
        if error.code not in ANCHOR_CODES:
            raise ValueError(f"unexpected span error: {error.code}") from error
        return error.code, None, None


def audit_response(raw: str, case: dict, event: dict, label: dict) -> dict:
    """Analyze one immutable response, including a clause-index-only copy."""
    clauses = frozen._clauses(case["user_message"])
    gold_event = frozen._span(event["event_span"], clauses, "event_span")
    parsed = frozen._json(raw)
    if type(parsed) is not dict or set(parsed) != frozen.GRAPH_FIELDS:
        raise ValueError("raw graph shape differs")

    statuses = {}
    anchors = {}
    repair_indexes = {}
    for field in SPAN_FIELDS:
        status, anchor, repaired_index = _anchor_status(parsed[field], clauses, field)
        statuses[field] = status
        anchors[field] = anchor
        if repaired_index is not None:
            repair_indexes[field] = repaired_index

    subject = anchors["subject_span"]
    cue = anchors["event_subject_evidence_span"]
    edge = parsed["target_edge_kind"]
    projection = RELATIONS.get(edge) if type(edge) is str else None
    gold_subject = event["hazard_owner_span"]
    result = {
        "anchor_status": statuses,
        "event_cue_overlaps_event": frozen._overlaps(cue, gold_event) if cue else None,
        "event_cue_overlaps_subject": frozen._overlaps(cue, subject) if cue and subject else None,
        "subject_raw_exact": parsed["subject_span"] == gold_subject,
        "gold_subject_present": gold_subject is not None,
        "attachment_kind_correct": parsed["event_subject_kind"] == label["event_subject_kind"],
        "edge_kind_correct": edge == label["target_edge_kind"],
        "attachment_evidence_raw_exact": parsed["event_subject_evidence_span"]
        == label["event_subject_evidence_span"],
        "edge_evidence_raw_exact": parsed["target_edge_evidence_span"]
        == label["target_edge_evidence_span"],
        "kind_projection": projection,
        "kind_projection_correct": projection == event["owner_to_target"],
        "repair_fields": sorted(repair_indexes),
    }

    # The original contract result remains unchanged. Never repair text, kind,
    # subject choice, or any semantic link; only unique clause indices in a copy.
    repaired = json.loads(json.dumps(parsed, ensure_ascii=False))
    for field, index in repair_indexes.items():
        repaired[field]["clause_index"] = index
    try:
        validated = frozen.replay_graph(
            json.dumps(repaired, ensure_ascii=False), case["user_message"], event["event_span"]
        )
    except frozen.ContractError as error:
        result["repair_contract_status"] = error.code
        result["repair_relation_correct"] = False
    else:
        result["repair_contract_status"] = "validated"
        result["repair_relation_correct"] = (
            validated["effective_relation"] == event["owner_to_target"]
        )
    return result


def audit(
    protocol_path: Path, journal_path: Path, verification_path: Path, private_dir: Path
) -> dict:
    """Verify immutable inputs/raw bytes, then derive a sanitized error matrix."""
    protocol_bytes = protocol_path.read_bytes()
    protocol = frozen._json(protocol_bytes.decode("utf-8"))
    verification = frozen._json(verification_path.read_text(encoding="utf-8"))
    journal_bytes = journal_path.read_bytes()
    journal_sha = frozen._digest(journal_bytes)
    protocol_sha = frozen._digest(protocol_bytes)
    if (
        type(protocol) is not dict
        or type(verification) is not dict
        or protocol_sha != verification.get("protocol_sha256")
        or journal_sha != verification.get("journal_sha256")
        or protocol.get("kind") != frozen.KIND
        or protocol.get("claim_scope") != frozen.SCOPE
        or protocol.get("case_order") != list(frozen.CASE_ORDER)
        or verification.get("kind") != frozen.KIND
        or protocol.get("input_hashes")
        != {name: frozen._digest_file(path) for name, path in frozen.INPUTS.items()}
        or frozen._digest_file(Path(frozen.__file__))
        != protocol["source_manifest"]["experiments/as_safety_evidence_graph_v1/verify.py"]
    ):
        raise ValueError("frozen input or verification identity differs")
    frozen._private_dir(private_dir)
    cases = load_cases(frozen.DATASET)
    labels = frozen.load_labels(frozen.LABELS, cases)
    rows = [frozen._json(line) for line in journal_bytes.decode("utf-8").splitlines()]
    if len(rows) != 2 + 2 * len(cases) or rows[0] != {
        "event": "header",
        "protocol_sha256": protocol_sha,
    }:
        raise ValueError("journal structure differs")
    audited = []
    for index, case in enumerate(cases):
        if rows[1 + 2 * index] != {"event": "begin", "case_id": case["id"]}:
            raise ValueError("journal order differs")
        audited.append(frozen.audit_end(rows[2 + 2 * index], case, private_dir))
    summary = frozen.summarize(audited, cases, labels)
    if rows[-1] != summary or verification.get("summary") != {
        key: value for key, value in summary.items() if key != "event"
    }:
        raise ValueError("journal or committed verification summary differs")
    expected_raw_names = {
        f"{case['id']}-graph-{index}.json.txt"
        for case in cases
        for index, event in enumerate(case["events"], 1)
        if event["occurrence"] != "nonoccurring"
    }
    if {path.name for path in private_dir.iterdir()} != expected_raw_names or verification.get(
        "private_raw_count"
    ) != len(expected_raw_names):
        raise ValueError("private raw inventory differs")

    findings = []
    for case, label_case, end in zip(cases, labels, rows[2:-1:2], strict=True):
        for index, (event, label, stage) in enumerate(
            zip(case["events"], label_case["events"], end["stages"], strict=True), 1
        ):
            if not stage["called"]:
                continue
            raw = frozen._read_raw(stage, private_dir / f"{case['id']}-graph-{index}.json.txt")
            if raw is None:
                raise ValueError("called stage has no raw response")
            result = audit_response(raw, case, event, label)
            findings.append(
                {
                    "case_id": case["id"],
                    "event_index": index,
                    "raw_sha256": stage["raw_sha256"],
                    "gold_category": f"{event['occurrence']}_{event['owner_to_target']}",
                    "original_status": stage["status"],
                    "original_first_error": stage["error_code"],
                    **result,
                }
            )
    if len(findings) != summary["request_count"]:
        raise ValueError("offline response count differs")

    return {
        "kind": "as_safety_evidence_graph_v1_posthoc_error_audit",
        "claim_scope": "exposed_development_set_posthoc_diagnostic_only",
        "protocol_sha256": protocol_sha,
        "journal_sha256": journal_sha,
        "source_verifier_sha256": frozen._digest_file(Path(frozen.__file__)),
        "raw_count": len(findings),
        "summary": {
            "original_contract_valid": sum(f["original_status"] == "validated" for f in findings),
            "format_only_repair_attempted": sum(bool(f["repair_fields"]) for f in findings),
            "format_only_contract_valid": sum(
                f["repair_contract_status"] == "validated" for f in findings
            ),
            "format_only_relation_correct": sum(f["repair_relation_correct"] for f in findings),
            "format_only_newly_valid": sum(
                f["original_status"] != "validated" and f["repair_contract_status"] == "validated"
                for f in findings
            ),
            "format_only_newly_relation_correct": sum(
                f["original_status"] != "validated" and f["repair_relation_correct"]
                for f in findings
            ),
            "kind_only_projection_correct": sum(f["kind_projection_correct"] for f in findings),
            "gold_category_counts": summary["category_counts"],
            "kind_only_projection_by_category": {
                category: sum(
                    f["kind_projection_correct"] for f in findings if f["gold_category"] == category
                )
                for category in summary["category_counts"]
            },
            "raw_subject_exact_nonnull": sum(
                f["subject_raw_exact"] and f["gold_subject_present"] for f in findings
            ),
            "raw_subject_null_correct": sum(
                f["subject_raw_exact"] and not f["gold_subject_present"] for f in findings
            ),
            "raw_attachment_kind_correct": sum(f["attachment_kind_correct"] for f in findings),
            "raw_edge_kind_correct": sum(f["edge_kind_correct"] for f in findings),
            "raw_attachment_evidence_exact": sum(
                f["attachment_evidence_raw_exact"] for f in findings
            ),
            "raw_edge_evidence_exact": sum(f["edge_evidence_raw_exact"] for f in findings),
            "anchor_status_counts": {
                field: dict(Counter(f["anchor_status"][field] for f in findings))
                for field in SPAN_FIELDS
            },
        },
        "events": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--verification", required=True, type=Path)
    parser.add_argument("--private-dir", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            audit(args.protocol, args.journal, args.verification, args.private_dir),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
