"""Reject malformed safety confirmation records before aggregate scoring."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from scripts.verify_nlu_safety_confirmation_pair import _verify_row


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
