"""Compare contextual and composed source rules on the reviewed DP pairs."""

import json
from pathlib import Path

from experiments.as_safety_contextual_part import contextual_source
from experiments.as_safety_device_part import composed_source
from experiments.as_safety_pair_evaluation import compare_with_locations

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout/as-safety-device-part-dp-reviewed.v1.json"


def evaluate() -> dict:
    return compare_with_locations(
        DATA,
        "as_safety_device_part_dp_reviewed_v1",
        {"contextual": contextual_source, "composed": composed_source},
    )


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
