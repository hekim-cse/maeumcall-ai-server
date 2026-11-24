"""Compare the SL role rule with the scoped rule on user-reviewed SQ pairs."""

import json
from pathlib import Path

from experiments.as_safety_pair_evaluation import compare
from experiments.as_safety_source_role import source_role
from experiments.as_safety_source_scope import source_scope

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout/as-safety-source-scope-sq-reviewed.v1.json"

if __name__ == "__main__":
    result = compare(
        DATA, "as_safety_source_scope_sq_reviewed_v1", {"role": source_role, "scope": source_scope}
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
