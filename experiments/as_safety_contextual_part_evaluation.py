"""Compare scoped and contextual source rules on user-reviewed CP pairs."""

import json
from pathlib import Path

from experiments.as_safety_contextual_part import contextual_source
from experiments.as_safety_pair_evaluation import compare
from experiments.as_safety_source_scope import source_scope

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout/as-safety-contextual-part-cp-reviewed.v1.json"

if __name__ == "__main__":
    result = compare(
        DATA,
        "as_safety_contextual_part_cp_reviewed_v1",
        {"scope": source_scope, "contextual": contextual_source},
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
