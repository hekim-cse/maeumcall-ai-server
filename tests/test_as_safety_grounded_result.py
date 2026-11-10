"""Recheck the saved development result without replaying model requests."""

import json
from pathlib import Path

import pytest

from scripts.verify_as_safety_grounded_development import verify

DATA = Path("evals/structured_nlu/data/ai_heldout")
PROTOCOL = DATA / "as-safety-grounded-exposed-development-protocol.v1.json"
JOURNAL = DATA / "as-safety-grounded-exposed-development-result.v1.jsonl"


def test_frozen_result_recomputes_failure_and_safety_boundary():
    result = verify(PROTOCOL, JOURNAL)
    assert result["summary"]["RE"]["candidate_correct"] == 2
    assert result["summary"]["V"]["candidate_correct"] == 9
    assert result["summary"]["RE"]["candidate_errors"] == 3
    by_id = {row["id"]: row for row in result["per_case"]}
    assert by_id["V06"]["candidate"] == "collecting_service_request"
    assert by_id["V09"]["candidate"] == "safety_action_required"


def test_saved_source_span_tampering_is_rejected(tmp_path):
    events = [json.loads(line) for line in JOURNAL.read_text(encoding="utf-8").splitlines()]
    record = next(
        row
        for row in events
        if row.get("event") == "end"
        and row.get("case_id") == "V06"
        and row.get("arm") == "candidate"
    )
    record["decision"]["anchor_relation"] = "current"
    altered = tmp_path / "changed.jsonl"
    altered.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in events) + "\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="anchor relation"):
        verify(PROTOCOL, altered)
