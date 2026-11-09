"""Regression checks for the frozen exposed-case development audit."""

import json
from pathlib import Path

import pytest

from scripts.verify_as_safety_entailment_development import verify

DATASET = Path("evals/structured_nlu/data/ai_heldout/as-safety-relation-fresh-reviewed.v1.json")
PROTOCOL = Path(
    "evals/structured_nlu/data/ai_heldout/as-safety-entailment-exposed-development-protocol.v1.json"
)
JOURNAL = Path(
    "evals/structured_nlu/data/ai_heldout/as-safety-entailment-exposed-development-result.v1.jsonl"
)


def test_frozen_development_result_reverifies():
    counts = verify(DATASET, PROTOCOL, JOURNAL)
    assert counts["all"]["baseline_correct"] == 9
    assert counts["all"]["candidate_correct"] == 4
    assert counts["all"]["candidate_errors"] == 2


def test_route_tamper_is_rejected(tmp_path):
    events = [json.loads(line) for line in JOURNAL.read_text().splitlines()]
    first_end = next(event for event in events if event["event"] == "end")
    first_end["route"] = "collecting_service_request"
    changed = tmp_path / "changed.jsonl"
    changed.write_text("\n".join(json.dumps(event) for event in events) + "\n")
    with pytest.raises(ValueError, match="route differs"):
        verify(DATASET, PROTOCOL, changed)
