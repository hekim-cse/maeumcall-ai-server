"""Score the offline source baseline against the reviewed EP candidate pairs."""

import hashlib
import json
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_explicit_source import explicit_source
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout/as-safety-explicit-source-ep-reviewed.v1.json"


def evaluate_candidate(case, record, kiwi):
    try:
        clauses = split_clauses(case["utterance"])
        event = anchor_span(case["event"], clauses, field="event")
        span = anchor_span(record["span"], clauses, field="candidate")
        if event is None or span is None:
            raise ValidationError("required_span_missing", record["id"])
        pair = FixedPair(case["utterance"], clauses, event, SourceCandidate(record["id"], **span))
        evidence = explicit_source(pair, case["occurrence"], kiwi)
    except (ValidationError, ValueError) as error:
        return {"decision": "error", "error": str(error), "evidence": None}
    return {
        "decision": "approve" if evidence is not None else "abstain",
        "error": None,
        "evidence": asdict(evidence) if evidence is not None else None,
    }


def evaluate(path=DATA):
    data = path.read_bytes()
    reviewed = json.loads(data)
    if reviewed["kind"] != "as_safety_explicit_source_ep_reviewed_v1":
        raise ValueError("unexpected fixture kind")
    cases = reviewed["cases"]
    if [case["id"] for case in cases] != [f"EP{i:02}" for i in range(1, 9)]:
        raise ValueError("reviewed case set or order differs")
    kiwi = Kiwi()
    rows = []
    pair_scores = {"mixed_total": 0, "mixed_pass": 0, "all_abstain_total": 0, "all_abstain_pass": 0}
    for case in cases:
        candidates = case["candidates"]
        if [item["id"] for item in candidates] != [f"{case['id']}-1", f"{case['id']}-2"]:
            raise ValueError("reviewed candidate IDs or order differ")
        group = []
        for item in candidates:
            if type(item["approve"]) is not bool:
                raise ValueError("approval label must be a boolean")
            predicted = evaluate_candidate(case, item, kiwi)
            gold = "approve" if item["approve"] else "abstain"
            group.append(
                {
                    "case": case["id"],
                    "candidate": item["id"],
                    "gold": gold,
                    **predicted,
                    "correct": predicted["decision"] == gold,
                }
            )
        rows.extend(group)
        category = "mixed" if any(row["gold"] == "approve" for row in group) else "all_abstain"
        pair_scores[f"{category}_total"] += 1
        pair_scores[f"{category}_pass"] += all(row["correct"] for row in group)

    positives = [row for row in rows if row["gold"] == "approve"]
    negatives = [row for row in rows if row["gold"] == "abstain"]
    return {
        "input_sha256": hashlib.sha256(data).hexdigest(),
        "kiwipiepy": version("kiwipiepy"),
        "kiwipiepy_model": version("kiwipiepy_model"),
        "summary": {
            "total_candidates": len(rows),
            "positive_total": len(positives),
            "true_approval": sum(row["decision"] == "approve" for row in positives),
            "missed_approval": sum(row["decision"] == "abstain" for row in positives),
            "negative_total": len(negatives),
            "false_approval": sum(row["decision"] == "approve" for row in negatives),
            "correct_abstention": sum(row["decision"] == "abstain" for row in negatives),
            "errors": sum(row["decision"] == "error" for row in rows),
            **pair_scores,
        },
        "rows": rows,
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
