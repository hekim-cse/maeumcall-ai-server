"""Compare source rules on the reviewed AP pairs."""

import json
from pathlib import Path

from experiments.as_safety_device_part import attached_device_source, surface_nominal_source
from experiments.as_safety_pair_evaluation import compare_with_locations

DATA = Path(__file__).resolve().parents[1] / (
    "evals/structured_nlu/data/ai_heldout/as-safety-attached-device-part-ap-reviewed.v1.json"
)


def evaluate() -> dict:
    return compare_with_locations(
        DATA,
        "as_safety_attached_device_part_ap_reviewed_v1",
        {"surface_nominal": surface_nominal_source, "attached_device": attached_device_source},
    )


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
