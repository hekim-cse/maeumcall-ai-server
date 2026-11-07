"""Reject altered PF counts, source bytes, raw text, and invalid actions."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.verify_nlu_safety_postfreeze_pair import verify

DATA = Path("evals/structured_nlu/data/ai_heldout")
RESULT = Path("evals/structured_nlu/results/nlu-safety-postfreeze-graph-pair-v1.json")
DATASET = DATA / "nlu-safety-postfreeze-reviewed.v1.json"
PROTOCOL = DATA / "nlu-safety-postfreeze-graph-pair-protocol.v1.json"


def test_frozen_postfreeze_result_recalculates() -> None:
    """Both reported group scores agree with their case-level predictions."""
    summary = verify(RESULT, DATASET, PROTOCOL)
    assert summary["baseline"]["safety_positive"]["entered_safety_state"] == 2
    assert summary["candidate"]["safety_negative"]["incorrectly_entered_safety_state"] == 0


@pytest.mark.parametrize("tampering", ["count", "raw", "contract"])
def test_altered_result_is_rejected(tmp_path: Path, tampering: str) -> None:
    """The verifier checks output meaning and forbids unbounded model text."""
    payload = json.loads(RESULT.read_text())
    if tampering == "count":
        payload["summaries"]["candidate"]["safety_positive"]["entered_safety_state"] = 8
    elif tampering == "raw":
        payload["results"]["baseline"][0]["attempts"][0]["raw"] = "model output"
    else:
        output = payload["results"]["candidate"][8]["attempts"][0]["output"]
        output["user_action"] = "unknown"
        output["fields"]["product_type"] = "공기청정기"
    changed = tmp_path / "result.json"
    changed.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        verify(changed, DATASET, PROTOCOL)


def test_result_rehash_cannot_hide_changed_dataset(tmp_path: Path) -> None:
    """A committed protocol remains the independent expected input digest."""
    dataset = json.loads(DATASET.read_text())
    dataset["cases"][0]["user_message"] += " 추가 문장"
    changed_dataset = tmp_path / "dataset.json"
    changed_dataset.write_text(json.dumps(dataset, ensure_ascii=False))
    payload = json.loads(RESULT.read_text())
    payload["dataset_sha256"] = hashlib.sha256(changed_dataset.read_bytes()).hexdigest()
    changed_result = tmp_path / "result.json"
    changed_result.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="pre-exposure protocol"):
        verify(changed_result, changed_dataset, PROTOCOL)
