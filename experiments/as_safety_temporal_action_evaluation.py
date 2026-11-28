"""Compare time-only, action-only, and combined source boundary changes."""

import hashlib
import json
from pathlib import Path

from experiments.as_safety_pair_evaluation import compare_with_locations, summarize
from experiments.as_safety_temporal_action import RULES

DATA = Path(__file__).resolve().parents[1] / (
    "evals/structured_nlu/data/ai_heldout/as-safety-temporal-action-reviewed.v1.json"
)
INPUT_SHA256 = "e6149885c16061e10fdb4987db57b8aa050d6fd721b19e7c1263b6821d10a490"


def evaluate() -> dict:
    raw = DATA.read_bytes()
    if hashlib.sha256(raw).hexdigest() != INPUT_SHA256:
        raise ValueError("reviewed input changed")
    result = compare_with_locations(DATA, "as_safety_temporal_action_reviewed_v1", RULES)
    if result["input_sha256"] != INPUT_SHA256:
        raise ValueError("reviewed input changed during comparison")
    other_ids = json.loads(raw)["other_event_source_candidates"]
    by_id = {row["id"]: row for row in result["rows"]}
    if len(other_ids) != len(set(other_ids)) or any(
        identifier not in by_id or by_id[identifier]["gold"] != "abstain"
        for identifier in other_ids
    ):
        raise ValueError("other-event sources must be unique abstention labels")
    for name, summary in result["summary"].items():
        summary["other_event_total"] = len(other_ids)
        summary["other_event_false_approval"] = sum(
            by_id[identifier][name] == "approve" for identifier in other_ids
        )
    result["groups"] = {}
    for prefix in ("TP", "AC", "MX"):
        rows = [row for row in result["rows"] if row["case"].startswith(prefix)]
        result["groups"][prefix] = {name: summarize(rows, name) for name in RULES}
    return result


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
