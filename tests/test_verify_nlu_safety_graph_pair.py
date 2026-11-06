"""Reject altered counts and accidental raw response retention."""

import hashlib
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


@pytest.mark.parametrize(
    "tampering", ["count", "raw_attempt", "raw_result", "raw_output", "contract"]
)
def test_tampered_result_is_rejected(tmp_path: Path, tampering: str) -> None:
    payload = json.loads(RESULT.read_text())
    if tampering == "count":
        payload["summaries"]["candidate"]["safety_positive"]["entered_safety_state"] = 8
    elif tampering == "raw_attempt":
        payload["results"]["baseline"][0]["attempts"][0]["raw"] = "model output"
    elif tampering == "raw_result":
        payload["results"]["baseline"][0]["raw"] = "model output"
    elif tampering == "raw_output":
        payload["results"]["baseline"][0]["attempts"][0]["output"]["raw"] = "model output"
    else:
        output = payload["results"]["candidate"][17]["attempts"][0]["output"]
        output["fields"]["product_type"] = "선풍기"
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        verify(changed, DATASET, PROTOCOL)


def test_changed_dataset_cannot_be_accepted_by_rehashing_result(tmp_path: Path) -> None:
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
