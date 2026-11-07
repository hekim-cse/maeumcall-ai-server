"""Bounded development evidence must match its exposed PF source cases."""

import hashlib
import json
from pathlib import Path


def test_safety_focus_result_counts_and_keeps_no_raw_text() -> None:
    """Recount diagnostic outcomes without treating them as heldout accuracy."""
    result = json.loads(
        Path("evals/structured_nlu/results/nlu-safety-focus-exposed-development-v1.json").read_text()
    )
    dataset = Path("evals/structured_nlu/data/ai_heldout/nlu-safety-postfreeze-reviewed.v1.json")
    assert result["dataset_sha256"] == hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert result["claim_scope"] == "already_exposed_ai_authored_pf_development_only"
    rows = result["cases"]
    assert [row["case_id"] for row in rows] == [
        f"nlu-safety-postfreeze-pf{i:02}" for i in range(1, 17)
    ]
    assert all(
        set(row) == {
            "case_id", "expected_safety", "current_safety_issue", "latency_ms", "error_type"
        }
        for row in rows
    )
    assert sum(row["current_safety_issue"] is True for row in rows[:8]) == 8
    assert sum(row["current_safety_issue"] is False for row in rows[8:]) == 4
    assert sum(row["error_type"] is not None for row in rows) == 3
    assert result["summary"]["positive_correct"] == 8
    assert result["summary"]["negative_correct"] == 4
    assert result["summary"]["invalid_responses"] == 3
