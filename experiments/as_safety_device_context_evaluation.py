"""Compare source rules on the reviewed DC pairs."""

import json
from pathlib import Path

from experiments.as_safety_device_context import device_context_source
from experiments.as_safety_device_part import attached_device_source
from experiments.as_safety_pair_evaluation import compare_with_locations

DATA = Path(__file__).resolve().parents[1] / (
    "evals/structured_nlu/data/ai_heldout/as-safety-device-context-dc-reviewed.v1.json"
)


def evaluate() -> dict:
    return compare_with_locations(
        DATA,
        "as_safety_device_context_dc_reviewed_v1",
        {"attached_device": attached_device_source, "device_context": device_context_source},
    )


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
