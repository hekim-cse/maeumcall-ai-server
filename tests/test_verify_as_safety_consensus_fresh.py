"""Recheck and tamper-test the frozen V01–V16 exploratory result."""

import hashlib
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


def test_changed_runner_source_hash_is_rejected(tmp_path):
    protocol = json.loads(PROTOCOL.read_text())
    protocol["runner_sha256"] = "0" * 64
    changed = tmp_path / "protocol.json"
    changed.write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="frozen runner_sha256 differs"):
        verify(DATASET, changed, JOURNAL)


def test_changed_entailment_gold_is_rejected_even_with_updated_hashes(tmp_path):
    dataset = json.loads(DATASET.read_text())
    dataset["cases"][0]["expected_entailment"] = {
        "hazard_index": 2,
        "claim": "contradicted",
        "reason": "other_source",
    }
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


@pytest.mark.parametrize(
    ("stage", "decision", "finish_reason", "message"),
    [
        ("route", {"some": "decision"}, "stop", "retains decision"),
        ("contract", None, "length", "postresponse error finish reason differs"),
        ("response", None, "stop", "response error finish reason differs"),
    ],
)
def test_error_metadata_tamper_is_rejected(tmp_path, stage, decision, finish_reason, message):
    events = [json.loads(line) for line in JOURNAL.read_text().splitlines()]
    failed = next(event for event in events if event.get("error_stage") == "contract")
    failed.update(error_stage=stage, decision=decision, finish_reason=finish_reason)
    changed = tmp_path / "journal.jsonl"
    changed.write_text("\n".join(json.dumps(event) for event in events) + "\n")
    with pytest.raises(ValueError, match=message):
        verify(DATASET, PROTOCOL, changed)
