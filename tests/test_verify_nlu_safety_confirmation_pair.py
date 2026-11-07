"""Reject malformed safety confirmation records before aggregate scoring."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals.structured_nlu.ai_heldout import AIHeldoutDataset
from scripts.verify_nlu_safety_confirmation_pair import _verify_row, verify

ROOT = Path("evals/structured_nlu/data/ai_heldout")
RESULT = ROOT / "nlu-safety-confirmation-graph-pair-result.v1.json"
DATASET = ROOT / "nlu-safety-confirmation-reviewed.v1.json"
GOALS = ROOT / "nlu-safety-confirmation-goals.v1.json"
PROTOCOL = ROOT / "nlu-safety-confirmation-graph-pair-protocol.v1.json"


def _row() -> dict:
    return {
        "case_id": "nlu-safety-confirmation-cf01",
        "model_request_count": 0,
        "attempts": [],
        "conversation_state": "safety_action_required",
        "workflow_status": "blocked",
        "safety_status": "safety_issue",
        "error_type": None,
        "focus_request_count": 0,
        "focus_attempts": [],
        "graph_latency_ms": 5.0,
    }


def test_direct_safety_row_requires_consistent_state() -> None:
    case = SimpleNamespace(id="nlu-safety-confirmation-cf01")
    _verify_row(case, _row(), "baseline")
    changed = _row()
    changed["workflow_status"] = "in_progress"
    with pytest.raises(ValueError, match="direct safety"):
        _verify_row(case, changed, "baseline")


def test_confirmation_requires_candidate_focus_and_no_raw_text() -> None:
    case = SimpleNamespace(id="nlu-safety-confirmation-cf01")
    row = _row()
    row.update(
        conversation_state="confirming_safety_status",
        safety_status=None,
        focus_request_count=1,
        focus_attempts=[{"decision": True, "error_type": None, "latency_ms": 3.0}],
    )
    _verify_row(case, row, "candidate")
    with pytest.raises(ValueError):
        _verify_row(case, row, "baseline")
    changed = deepcopy(row)
    changed["focus_attempts"][0]["raw"] = "model completion"
    with pytest.raises(ValueError, match="focused attempt keys"):
        _verify_row(case, changed, "candidate")
    changed = deepcopy(row)
    changed["focus_attempts"][0]["decision"] = False
    with pytest.raises(ValueError, match="confirmation provenance"):
        _verify_row(case, changed, "candidate")


def test_extracted_safety_issue_requires_direct_safety_state() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    row = deepcopy(result["results"]["baseline"][2])
    assert row["attempts"][-1]["output"]["fields"]["safety_status"] == "safety_issue"
    row.update(conversation_state="collecting_service_request", workflow_status="in_progress")
    case = AIHeldoutDataset.model_validate_json(DATASET.read_bytes()).cases[2]
    with pytest.raises(ValueError, match="extracted safety issue"):
        _verify_row(case, row, "baseline")


def test_frozen_result_hashes_and_summaries_are_independently_checked(tmp_path: Path) -> None:
    summaries = verify(RESULT, DATASET, GOALS, PROTOCOL)
    assert summaries["candidate"]["confirmed_hazard"]["safety_confirmation"] == 10
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    result["dataset_sha256"] = "0" * 64
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ValueError, match="dataset_sha256"):
        verify(changed, DATASET, GOALS, PROTOCOL)
    result["dataset_sha256"] = json.loads(RESULT.read_text(encoding="utf-8"))["dataset_sha256"]
    result["summaries"]["candidate"]["confirmed_hazard"]["safety_confirmation"] = 9
    changed.write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ValueError, match="summary differs"):
        verify(changed, DATASET, GOALS, PROTOCOL)


def test_replay_result_requires_actual_alternating_order(tmp_path: Path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    protocol["kind"] = "ai_authored_safety_confirmation_pair_protocol_v2"
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    result["kind"] = "ai_authored_safety_confirmation_pair_result_v2"
    result["claim_scope"] = "same_32_case_replay_after_v1_exposure_for_order_provenance"
    result["protocol_sha256"] = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    result["execution_order"] = [
        {"case_id": case_id, "role": role}
        for index, case_id in enumerate(row["case_id"] for row in result["results"]["baseline"])
        for role in (("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline"))
    ]
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")
    verify(result_path, DATASET, GOALS, protocol_path)
    result["execution_order"][0]["role"] = "candidate"
    result_path.write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ValueError, match="execution order"):
        verify(result_path, DATASET, GOALS, protocol_path)
