"""Compare source rules on the reviewed OP pairs."""

import json
from pathlib import Path

from experiments.as_safety_device_context import device_context_source
from experiments.as_safety_device_operation import device_operation_source
from experiments.as_safety_pair_evaluation import compare_with_locations

DATA = Path(__file__).resolve().parents[1] / (
    "evals/structured_nlu/data/ai_heldout/as-safety-device-operation-op-reviewed.v1.json"
)


def evaluate() -> dict:
    return compare_with_locations(
        DATA,
        "as_safety_device_operation_op_reviewed_v1",
        {"device_context": device_context_source, "device_operation": device_operation_source},
    )


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
