"""Fresh safety exploration must require reviewed input and reject changed artifacts."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.run_as_safety_event_gate_fresh import load_reviewed_cases, summarize
from scripts.verify_as_safety_event_gate_fresh import verify


def _case(number: int) -> dict[str, str]:
    return {
        "id": f"EG{number:02}",
        "user_message": f"제품 {number}의 버튼을 확인하고 싶습니다.",
        "expected_route": (
            "safety_action_required"
            if number <= 8
            else "confirming_safety_status"
            if number <= 16
            else "collecting_service_request"
        ),
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    dataset = tmp_path / "dataset.json"
    dataset.write_text(
        json.dumps(
            {
                "kind": "as_safety_event_gate_ai_reviewed_v1",
                "provenance": "ai_authored",
                "review_status": "owner_approved_for_exploration",
                "cases": [_case(number) for number in range(1, 33)],
            },
            ensure_ascii=False,
        )
    )
    protocol = tmp_path / "protocol.json"
    protocol.write_text(
        json.dumps(
            {
                "kind": "as_safety_event_gate_fresh_protocol_v1",
                "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
            }
        )
    )
    rows = [
        {
            "case_id": f"EG{number:02}",
            "clause_count": 1,
            "evidence_index": None,
            "target": "none",
            "assertion": "none",
            "model_route": "collecting_service_request",
            "gate_route": "collecting_service_request",
            "gate_reason": "model_route_unchanged",
            "error_type": None,
            "latency_ms": 1.0,
        }
        for number in range(1, 33)
    ]
    result = tmp_path / "result.json"
    result.write_text(
        json.dumps(
            {
                "kind": "as_safety_event_gate_fresh_result_v1",
                "claim_scope": "ai_authored_owner_reviewed_targeted_exploration",
                "protocol_sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
                "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
                "summary": summarize([_case(number) for number in range(1, 33)], rows),
                "rows": rows,
            }
        )
    )
    return dataset, protocol, result


def test_reviewed_dataset_and_result_contract_accept_consistent_artifact(tmp_path: Path) -> None:
    dataset, protocol, result = _fixture(tmp_path)
    cases, digest = load_reviewed_cases(dataset)
    assert len(cases) == 32
    assert digest == hashlib.sha256(dataset.read_bytes()).hexdigest()
    verify(dataset, protocol, result)


@pytest.mark.parametrize(
    "change",
    ["unreviewed", "duplicate_id", "unknown_route", "extra_case_field"],
)
def test_reviewed_dataset_rejects_invalid_inputs(tmp_path: Path, change: str) -> None:
    dataset, _, _ = _fixture(tmp_path)
    payload = json.loads(dataset.read_text())
    if change == "unreviewed":
        payload["review_status"] = "draft"
    elif change == "duplicate_id":
        payload["cases"][1]["id"] = "EG01"
    elif change == "unknown_route":
        payload["cases"][0]["expected_route"] = "unknown"
    else:
        payload["cases"][0]["raw_model_response"] = "should not exist"
    dataset.write_text(json.dumps(payload, ensure_ascii=False))
    with pytest.raises(ValueError):
        load_reviewed_cases(dataset)


@pytest.mark.parametrize(
    "change",
    ["raw_text", "bad_index", "bad_route", "bad_summary", "infinite_latency", "bad_digest"],
)
def test_fresh_verifier_rejects_mutated_artifact(tmp_path: Path, change: str) -> None:
    dataset, protocol, result_path = _fixture(tmp_path)
    result = copy.deepcopy(json.loads(result_path.read_text()))
    if change == "raw_text":
        result["rows"][0]["user_message"] = "private utterance"
    elif change == "bad_index":
        result["rows"][0]["evidence_index"] = 999
    elif change == "bad_route":
        result["rows"][0]["gate_route"] = "safety_action_required"
    elif change == "bad_summary":
        result["summary"]["confirmed_hazard"]["gate_direct"] += 1
    elif change == "infinite_latency":
        result["rows"][0]["latency_ms"] = float("inf")
    else:
        result["dataset_sha256"] = "0" * 64
    result_path.write_text(json.dumps(result, ensure_ascii=False))
    with pytest.raises(ValueError):
        verify(dataset, protocol, result_path)
