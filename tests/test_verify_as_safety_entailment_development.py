"""Regression checks for the frozen exposed-case development audit."""

import hashlib
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


def test_changed_frozen_executor_hash_is_rejected(tmp_path):
    protocol = json.loads(PROTOCOL.read_text())
    protocol["executor_sha256"] = "0" * 64
    changed = tmp_path / "protocol.json"
    changed.write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="frozen executor_sha256 differs"):
        verify(DATASET, changed, JOURNAL)


def test_changed_gold_is_rejected_even_with_updated_hashes(tmp_path):
    dataset = json.loads(DATASET.read_text())
    dataset["cases"][0]["expected_relation"]["target_relation"] = "other"
    changed_dataset = tmp_path / "dataset.json"
    changed_dataset.write_text(json.dumps(dataset))
    protocol = json.loads(PROTOCOL.read_text())
    protocol["dataset_sha256"] = hashlib.sha256(changed_dataset.read_bytes()).hexdigest()
    changed_protocol = tmp_path / "protocol.json"
    changed_protocol.write_text(json.dumps(protocol))
    events = [json.loads(line) for line in JOURNAL.read_text().splitlines()]
    events[0]["protocol_sha256"] = hashlib.sha256(changed_protocol.read_bytes()).hexdigest()
    changed_journal = tmp_path / "journal.jsonl"
    changed_journal.write_text("\n".join(json.dumps(event) for event in events) + "\n")
    with pytest.raises(ValueError, match="reviewed gold route differs"):
        verify(changed_dataset, changed_protocol, changed_journal)
