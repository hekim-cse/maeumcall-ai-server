"""Compare fixed pad candidates and replay the same exposed ES catalog."""

import json
from pathlib import Path

from experiments.as_safety_adjacent_pad_source import DETECTORS
from experiments.as_safety_pair_evaluation import compare_with_locations
from experiments.as_safety_wire_coordination_evaluation import baseline_projection, read_fixed
from scripts.audit_as_safety_source_selection import audit

ROOT = Path(__file__).resolve().parents[1]
KIND = "as_safety_adjacent_pad_reviewed_v1"
DATA = ROOT / "evals/structured_nlu/data/ai_heldout/as-safety-adjacent-pad-reviewed.v1.json"
DATA_SHA256 = "9e3e8bd7f814afe089496b100ce56dce947fb2e66f47c0f2b9f41beed0cc0797"
PRIOR = ROOT / "evals/structured_nlu/results/as-safety-wire-coordination-evaluation.v1.json"
PRIOR_SHA256 = "0e4b4001b27c60fdf453a272ac2cad43adf5b80bcec2022d298fb8c3e4d9a82c"


def paired_evaluation() -> dict:
    data = read_fixed(DATA, DATA_SHA256)
    result = compare_with_locations(DATA, KIND, DETECTORS)
    if result["input_sha256"] != DATA_SHA256:
        raise ValueError("reviewed input changed during comparison")
    for label in ("other_event_source", "partial_span"):
        ids = data[f"{label}_candidates"]
        subset = set(ids)
        rows = [row for row in result["rows"] if row["id"] in subset]
        if len(rows) != len(ids) or any(row["gold"] != "abstain" for row in rows):
            raise ValueError(f"{label} must consist of unique abstention labels")
        for name, summary in result["summary"].items():
            summary[f"{label}_total"] = len(rows)
            summary[f"{label}_false_approval"] = sum(row[name] == "approve" for row in rows)
    return result


def es_evaluation() -> dict:
    prior = read_fixed(PRIOR, PRIOR_SHA256)["es"]
    current = audit(DETECTORS)
    if baseline_projection(current, "baseline") != baseline_projection(prior, "combined"):
        raise ValueError("prior ES baseline was not reproduced")
    return {
        **current,
        "kind": "as_safety_es_adjacent_pad_development_v1",
        "historical_result_sha256": PRIOR_SHA256,
        "changed_events": [
            row["event"]
            for row in current["rows"]
            if row["rules"]["baseline"] != row["rules"]["adjacent_pad"]
        ],
    }


if __name__ == "__main__":
    print(
        json.dumps(
            {"paired": paired_evaluation(), "es": es_evaluation()}, ensure_ascii=False, indent=2
        )
    )
