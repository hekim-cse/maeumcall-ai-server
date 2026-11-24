"""Compare the previous and surface-recovery rules on the reviewed SN pairs."""

import json
from pathlib import Path

from experiments.as_safety_device_part import composed_source, surface_nominal_source
from experiments.as_safety_pair_evaluation import compare_with_locations

DATA = Path(__file__).resolve().parents[1] / (
    "evals/structured_nlu/data/ai_heldout/as-safety-surface-nominal-sn-reviewed.v1.json"
)


def evaluate() -> dict:
    return compare_with_locations(
        DATA,
        "as_safety_surface_nominal_sn_reviewed_v1",
        {"composed": composed_source, "surface_nominal": surface_nominal_source},
    )


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
