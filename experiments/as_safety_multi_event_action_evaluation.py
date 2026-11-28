"""Compare event-local source decisions and replay AC05 separately."""

import hashlib
import json
from pathlib import Path

from experiments.as_safety_multi_event_action import DETECTORS
from experiments.as_safety_pair_evaluation import compare_with_locations, summarize
from experiments.as_safety_temporal_action_evaluation import DATA as PRIOR_DATA
from experiments.as_safety_temporal_action_evaluation import INPUT_SHA256 as PRIOR_SHA256

DATA = Path(__file__).resolve().parents[1] / (
    "evals/structured_nlu/data/ai_heldout/as-safety-multi-event-action-reviewed.v1.json"
)
INPUT_SHA256 = "70b6967ff17108a9201e999435e261bd56f3f464887547edeffc3dcccbdab5d9"


def evaluate() -> dict:
    raw = DATA.read_bytes()
    if hashlib.sha256(raw).hexdigest() != INPUT_SHA256:
        raise ValueError("reviewed input changed")
    metadata = json.loads(raw)
    result = compare_with_locations(DATA, "as_safety_multi_event_action_reviewed_v1", DETECTORS)
    if result["input_sha256"] != INPUT_SHA256:
        raise ValueError("reviewed input changed during comparison")
    other_ids = set(metadata["other_event_source_candidates"])
    other_rows = [row for row in result["rows"] if row["id"] in other_ids]
    if len(other_rows) != len(metadata["other_event_source_candidates"]) or any(
        row["gold"] != "abstain" for row in other_rows
    ):
        raise ValueError("other-event sources must be unique abstention labels")
    for name, summary in result["summary"].items():
        summary["other_event_total"] = len(other_rows)
        summary["other_event_false_approval"] = sum(row[name] == "approve" for row in other_rows)
    first_ids = set(metadata["first_event_cases"])
    first_rows = [row for row in result["rows"] if row["case"] in first_ids]
    if len(first_rows) != 2 * len(metadata["first_event_cases"]):
        raise ValueError("first-event cases must be unique valid case IDs")
    result["first_event_summary"] = {name: summarize(first_rows, name) for name in DETECTORS}

    prior = compare_with_locations(PRIOR_DATA, "as_safety_temporal_action_reviewed_v1", DETECTORS)
    if prior["input_sha256"] != PRIOR_SHA256:
        raise ValueError("prior reviewed input changed")
    result["ac05_regression"] = [row for row in prior["rows"] if row["case"] == "AC05"]
    result["other_prior_changes"] = [
        row
        for row in prior["rows"]
        if row["case"] != "AC05" and row["baseline"] != row["multi_event"]
    ]
    return result


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
