"""Bounded development evidence must match its exposed PF source cases."""

import hashlib
import json
import statistics
from pathlib import Path


def test_safety_focus_result_counts_and_keeps_no_raw_text() -> None:
    """Recount diagnostic outcomes without treating them as heldout accuracy."""
    result = json.loads(
        Path(
            "evals/structured_nlu/results/nlu-safety-focus-exposed-development-v1.json"
        ).read_text()
    )
    dataset = Path("evals/structured_nlu/data/ai_heldout/nlu-safety-postfreeze-reviewed.v1.json")
    assert result["dataset_sha256"] == hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert result["claim_scope"] == "already_exposed_ai_authored_pf_development_only"
    assert (
        result["request_policy_sha256"]
        == "874e01d15f3185a11846f4d84c837d56dd23d2db3e2bf23da6843d1d71724133"
    )
    assert (
        result["probe_sha256"] == "a7d06348024a2fa79212abe5ab7316779ab027cd882d6997d77d729cbd38c556"
    )
    assert (
        result["model_sha256"] == "644b04cde835d486df33c6d4d7552ba367fcb28802fe39b6b4bb9c60b9ab6f3d"
    )
    assert result["max_tokens"] == 48
    rows = result["cases"]
    assert [row["case_id"] for row in rows] == [
        f"nlu-safety-postfreeze-pf{i:02}" for i in range(1, 17)
    ]
    assert all(
        set(row)
        == {"case_id", "expected_safety", "current_safety_issue", "latency_ms", "error_type"}
        for row in rows
    )
    assert sum(row["current_safety_issue"] is True for row in rows[:8]) == 8
    assert sum(row["current_safety_issue"] is False for row in rows[8:]) == 4
    assert sum(row["error_type"] is not None for row in rows) == 3
    assert [row["expected_safety"] for row in rows] == [True] * 8 + [False] * 8
    assert [row["error_type"] for row in rows] == [None] * 9 + [
        "ValueError",
        "ValueError",
        None,
        None,
        None,
        None,
        "JSONDecodeError",
    ]
    assert result["summary"]["positive_correct"] == 8
    assert result["summary"]["negative_correct"] == 4
    assert result["summary"]["invalid_responses"] == 3
    assert result["summary"]["positive_denominator"] == 8
    assert result["summary"]["negative_denominator"] == 8
    assert result["summary"]["median_latency_ms"] == round(
        statistics.median(row["latency_ms"] for row in rows), 3
    )
