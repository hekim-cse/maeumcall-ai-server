"""Reject altered counts and accidental raw response retention."""

import json
from pathlib import Path

import pytest

from scripts.verify_nlu_safety_graph_pair import verify

DATA = Path("evals/structured_nlu/data/ai_heldout")
RESULT = Path("evals/structured_nlu/results/nlu-safety-contract-graph-pair-v1.json")
DATASET = DATA / "nlu-safety-contract-reviewed.v1.json"
PROTOCOL = DATA / "nlu-safety-contract-graph-pair-protocol.v1.json"


def test_committed_result_recalculates() -> None:
    summary = verify(RESULT, DATASET, PROTOCOL)
    assert summary["candidate"]["safety_positive"]["entered_safety_state"] == 4
    assert summary["candidate"]["safety_negative"]["incorrectly_entered_safety_state"] == 1


@pytest.mark.parametrize("tampering", ["count", "raw"])
def test_tampered_result_is_rejected(tmp_path: Path, tampering: str) -> None:
    payload = json.loads(RESULT.read_text())
    if tampering == "count":
        payload["summaries"]["candidate"]["safety_positive"]["entered_safety_state"] = 8
    else:
        payload["results"]["baseline"][0]["attempts"][0]["raw"] = "model output"
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        verify(changed, DATASET, PROTOCOL)
