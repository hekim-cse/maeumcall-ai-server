"""Paired offline comparison on a single frozen source-role development fixture."""

import hashlib
import json
from collections import Counter
from importlib.metadata import version

from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_explicit_source import explicit_source
from experiments.as_safety_explicit_source_evaluation import DATA
from experiments.as_safety_source_role import source_role
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate

FIXTURE = DATA.with_name("as-safety-source-role-development.v1.json")


def evaluate() -> dict:
    raw = FIXTURE.read_bytes()
    fixture = json.loads(raw)
    if fixture["kind"] != "as_safety_source_role_development_v1":
        raise ValueError("unexpected fixture kind")
    kiwi = Kiwi()
    versions = {"baseline": explicit_source, "role": source_role}
    metrics = (
        "positive_total",
        "negative_total",
        "true_approval",
        "missed_approval",
        "false_approval",
        "correct_abstention",
        "errors",
        "pairs_total",
        "pairs_passed",
    )
    totals = {name: Counter(dict.fromkeys(metrics, 0)) for name in versions}
    rows = []
    for case in fixture["cases"]:
        clauses = split_clauses(case["utterance"])
        event = anchor_span(case["event"], clauses, field="event")
        pair_results = {name: [] for name in versions}
        for index, item in enumerate(case["candidates"], 1):
            identifier = f"{case['id']}-{index}"
            span = anchor_span(
                {"clause_index": item.get("clause_index", 1), "quote": item["quote"]},
                clauses,
                field=identifier,
            )
            if event is None or span is None or type(item["approve"]) is not bool:
                raise ValueError(f"invalid reviewed test input: {identifier}")
            pair = FixedPair(case["utterance"], clauses, event, SourceCandidate(identifier, **span))
            row = {"id": identifier, "quote": item["quote"], "gold_approval": item["approve"]}
            for name, detector in versions.items():
                counts = totals[name]
                approval = None
                counts["positive_total" if item["approve"] else "negative_total"] += 1
                try:
                    approval = detector(pair, "observed", kiwi) is not None
                except (ValidationError, ValueError):
                    counts["errors"] += 1
                if approval is not None:
                    if item["approve"]:
                        counts["true_approval" if approval else "missed_approval"] += 1
                    else:
                        counts["false_approval" if approval else "correct_abstention"] += 1
                row[name] = approval
                pair_results[name].append(approval == item["approve"])
            rows.append(row)
        for name, results in pair_results.items():
            totals[name]["pairs_total"] += 1
            totals[name]["pairs_passed"] += all(results)
    return {
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "kiwipiepy": version("kiwipiepy"),
        "kiwipiepy_model": version("kiwipiepy_model"),
        "summary": {name: dict(counts) for name, counts in totals.items()},
        "rows": rows,
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
