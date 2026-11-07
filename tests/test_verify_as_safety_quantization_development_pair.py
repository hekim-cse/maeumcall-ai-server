"""The Q4/Q5 development verifier must reject changed decisions and provenance."""

import copy
import json
from pathlib import Path

import pytest

from scripts.verify_as_safety_quantization_development_pair import verify

ROOT = Path("evals/structured_nlu/data/ai_heldout")
DATASET = ROOT / "nlu-safety-confirmation-reviewed.v1.json"
PROTOCOL = ROOT / "as-safety-exposed-q4-q5-development-pair-protocol.v1.json"
RESULT = ROOT / "as-safety-exposed-q4-q5-development-pair-result.v1.json"


def test_frozen_development_pair_recalculates() -> None:
    verify(DATASET, PROTOCOL, RESULT)


@pytest.mark.parametrize("change", ["route", "order", "extra", "index", "summary", "digest"])
def test_development_verifier_rejects_mutations(tmp_path: Path, change: str) -> None:
    result = copy.deepcopy(json.loads(RESULT.read_text(encoding="utf-8")))
    if change == "route":
        result["results"]["q5"][0]["route"] = "collecting_service_request"
    elif change == "order":
        result["execution_order"][0], result["execution_order"][1] = (
            result["execution_order"][1],
            result["execution_order"][0],
        )
    elif change == "extra":
        result["results"]["q4"][0]["evidence"] = "원문 유출"
    elif change == "index":
        result["results"]["q5"][0]["evidence_index"] = 999
    elif change == "summary":
        result["summaries"]["q5"]["confirmed_hazard"]["direct_safety"] += 1
    else:
        result["dataset_sha256"] = "0" * 64
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        verify(DATASET, PROTOCOL, changed)
