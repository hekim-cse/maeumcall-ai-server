"""Check reviewed input before the first V-case model exposure."""

import json
from pathlib import Path

import pytest

from scripts.run_as_safety_consensus_fresh import load_reviewed

DATASET = Path("evals/structured_nlu/data/ai_heldout/as-safety-relation-v2-fresh-reviewed.v1.json")


def test_reviewed_v_input_is_accepted():
    assert [case["id"] for case in load_reviewed(DATASET)] == [
        f"V{number:02}" for number in range(1, 17)
    ]


def test_reviewed_v_input_rejects_changed_gold(tmp_path):
    payload = json.loads(DATASET.read_text())
    payload["cases"][0]["expected_relation"]["target_relation"] = "other"
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="relation and route disagree"):
        load_reviewed(changed)
