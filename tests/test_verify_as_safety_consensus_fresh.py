"""Recheck and tamper-test the frozen V01–V16 exploratory result."""

import json
from pathlib import Path

import pytest

from scripts.verify_as_safety_consensus_fresh import verify

DATASET = Path("evals/structured_nlu/data/ai_heldout/as-safety-relation-v2-fresh-reviewed.v1.json")
PROTOCOL = Path("evals/structured_nlu/data/ai_heldout/as-safety-consensus-fresh-protocol.v1.json")
JOURNAL = Path("evals/structured_nlu/data/ai_heldout/as-safety-consensus-fresh-result.v1.jsonl")


def test_frozen_v_result_reverifies():
    summary = verify(DATASET, PROTOCOL, JOURNAL)["summary"]
    assert summary["current_hazard"]["baseline_direct"] == 7
    assert summary["current_hazard"]["consensus_direct"] == 6
    assert summary["other_source"]["consensus_direct"] == 1
    assert summary["all"]["arm_errors"] == 1


def test_decision_route_tamper_is_rejected(tmp_path):
    events = [json.loads(line) for line in JOURNAL.read_text().splitlines()]
    first_end = next(event for event in events if event["event"] == "end")
    first_end["route"] = "collecting_service_request"
    changed = tmp_path / "changed.jsonl"
    changed.write_text("\n".join(json.dumps(event) for event in events) + "\n")
    with pytest.raises(ValueError, match="route differs"):
        verify(DATASET, PROTOCOL, changed)
