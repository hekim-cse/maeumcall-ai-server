"""Compare contextual and composed source rules on the reviewed DP pairs."""

import hashlib
import json
from pathlib import Path

from experiments.as_safety_contextual_part import contextual_source
from experiments.as_safety_device_part import composed_source
from experiments.as_safety_pair_evaluation import compare

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout/as-safety-device-part-dp-reviewed.v1.json"


def evaluate() -> dict:
    frozen = DATA.read_bytes()
    location_ids = json.loads(frozen)["observation_location_candidates"]
    result = compare(
        DATA,
        "as_safety_device_part_dp_reviewed_v1",
        {"contextual": contextual_source, "composed": composed_source},
    )
    if result["input_sha256"] != hashlib.sha256(frozen).hexdigest():
        raise ValueError("reviewed fixture changed during evaluation")
    rows = {row["id"]: row for row in result["rows"]}
    location_rows = [rows[candidate] for candidate in location_ids]
    if len(location_ids) != len(set(location_ids)) or any(
        row["gold"] != "abstain" for row in location_rows
    ):
        raise ValueError("location subset must contain unique abstention labels")
    for name, summary in result["summary"].items():
        summary["location_total"] = len(location_rows)
        summary["location_false_approval"] = sum(row[name] == "approve" for row in location_rows)
    return result


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
