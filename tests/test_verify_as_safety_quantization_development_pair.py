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


@pytest.mark.parametrize(
    "change",
    [
        "route",
        "order",
        "extra",
        "index",
        "summary",
        "digest",
        "target_enum",
        "assertion_enum",
        "error_decision",
        "error_type",
        "clause_count",
        "negative_latency",
        "infinite_latency",
        "nan_latency",
    ],
)
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
    elif change == "target_enum":
        result["results"]["q5"][0]["target"] = "invalid"
    elif change == "assertion_enum":
        result["results"]["q5"][0]["assertion"] = "invalid"
    elif change == "error_decision":
        result["results"]["q4"][20]["route"] = "collecting_service_request"
    elif change == "error_type":
        result["results"]["q4"][20]["error_type"] = "UnexpectedError"
    elif change == "clause_count":
        result["results"]["q5"][0]["clause_count"] += 1
    elif change == "negative_latency":
        result["results"]["q5"][0]["latency_ms"] = -1
    elif change == "infinite_latency":
        result["results"]["q4"][20]["latency_ms"] = float("inf")
    elif change == "nan_latency":
        result["results"]["q4"][20]["latency_ms"] = float("nan")
    else:
        result["dataset_sha256"] = "0" * 64
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        verify(DATASET, PROTOCOL, changed)
