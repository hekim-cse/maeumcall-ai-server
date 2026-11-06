"""The published score verifier rejects incomplete retry records."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.verify_nlu_scope_revision_pair import verify

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
RESULT = ROOT / "evals/structured_nlu/results/nlu-scope-code-pair-v3.json"


def test_failed_first_attempt_requires_a_recorded_retry(tmp_path) -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    target = next(
        prediction
        for prediction in result["predictions"]["baseline"]
        if len(prediction["attempts"]) == 2 and not prediction["attempts"][0]["contract_valid"]
    )
    target["attempts"] = target["attempts"][:1]
    damaged = tmp_path / "incomplete.json"
    damaged.write_text(json.dumps(result), encoding="utf-8")

    with pytest.raises(ValueError, match="was not retried"):
        verify(
            DATA / "nlu-scope-reviewed.v2.json",
            DATA / "nlu-scope-review-ledger.v2.json",
            DATA / "nlu-scope-code-pair-protocol.v3.json",
            damaged,
        )
