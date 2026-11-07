"""The reviewed CF corpus and graph goals share one frozen case order."""

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from evals.structured_nlu.ai_heldout import load_reviewed_ai_heldout
from scripts import materialize_nlu_safety_confirmation_dataset as materialize

ROOT = Path("evals/structured_nlu/data/ai_heldout")
DATASET = ROOT / "nlu-safety-confirmation-reviewed.v1.json"
LEDGER = ROOT / "nlu-safety-confirmation-ledger.v1.json"
GOALS = ROOT / "nlu-safety-confirmation-goals.v1.json"


def test_reviewed_cf_inputs_and_graph_goals_agree() -> None:
    reviewed = load_reviewed_ai_heldout(
        DATASET,
        LEDGER,
        expected_scenario_keys=frozenset({"고객센터:a/s 접수"}),
    )
    goals = json.loads(GOALS.read_text(encoding="utf-8"))
    cases = reviewed.dataset.cases
    assert goals["kind"] == "ai_authored_safety_confirmation_goals_v1"
    assert goals["dataset_sha256"] == hashlib.sha256(DATASET.read_bytes()).hexdigest()
    assert [case.id for case in cases] == [
        f"nlu-safety-confirmation-cf{number:02}" for number in range(1, 33)
    ]
    assert [goal["case_id"] for goal in goals["goals"]] == [case.id for case in cases]
    assert Counter(goal["expected_state"] for goal in goals["goals"]) == {
        "safety_action_required": 12,
        "confirming_safety_status": 8,
        "collecting_service_request": 12,
    }
    assert all(case.provenance == "ai_authored" for case in cases)
    assert all(case.review_status == "adjudicated" for case in cases)


def test_duplicate_review_row_is_rejected_before_materialization(tmp_path: Path) -> None:
    original = materialize.REVIEW.read_text(encoding="utf-8")
    duplicate = next(line for line in original.splitlines() if line.startswith("| CF01 |"))
    review = tmp_path / "review.md"
    review.write_text(original + "\n" + duplicate + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate CF ID"):
        materialize._rows(review)


def test_reviewed_direction_is_fixed_for_all_groups(tmp_path: Path, monkeypatch) -> None:
    original = materialize.REVIEW.read_text(encoding="utf-8")
    changed = original.replace(
        "| 현상은 있으나 위험 여부 미확정 |", "| 현재 A/S 대상의 실제 위험 |", 1
    )
    review = tmp_path / "review.md"
    review.write_text(changed, encoding="utf-8")
    monkeypatch.setattr(materialize, "REVIEW", review)
    with pytest.raises(ValueError, match="direction differs: CF13"):
        materialize.main()
