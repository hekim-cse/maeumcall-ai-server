"""Check approved RE input and independent result integrity boundaries."""

import json

import pytest

from scripts.run_as_safety_relation_pair import load_reviewed, summarize
from scripts.verify_as_safety_relation_pair import verify


def test_reviewed_relation_cases_are_ordered_and_bounded():
    from pathlib import Path

    cases, digest = load_reviewed(
        Path("evals/structured_nlu/data/ai_heldout/as-safety-relation-fresh-reviewed.v1.json")
    )
    assert [case["id"] for case in cases] == [f"RE{index:02}" for index in range(1, 17)]
    assert len(digest) == 64


def test_reviewed_relation_cases_reject_changed_gold(tmp_path):
    from pathlib import Path

    source = Path("evals/structured_nlu/data/ai_heldout/as-safety-relation-fresh-reviewed.v1.json")
    payload = json.loads(source.read_text())
    payload["cases"][0]["expected_relation"]["hazard_index"] = 3
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="source index"):
        load_reviewed(changed)


def test_summary_keeps_errors_separate():
    rows = [
        {f"{arm}_{field}": None for arm in ("baseline", "relation") for field in ("route", "error")}
        for _ in range(16)
    ]
    rows[0]["baseline_route"] = "safety_action_required"
    rows[0]["relation_error"] = "TimeoutError"
    summary = summarize(rows)
    assert summary["confirmed_hazard"]["baseline_direct"] == 1
    assert summary["confirmed_hazard"]["relation_errors"] == 1


def test_verifier_rejects_protocol_mismatch(tmp_path):
    dataset = tmp_path / "dataset.json"
    protocol = tmp_path / "protocol.json"
    result = tmp_path / "result.json"
    dataset.write_text(json.dumps({"review_status": "owner_approved_for_exploration"}))
    protocol.write_text(json.dumps({"dataset_sha256": "0" * 64}))
    result.write_text("{}")
    with pytest.raises(ValueError, match="protocol dataset hash"):
        verify(dataset, protocol, result)
