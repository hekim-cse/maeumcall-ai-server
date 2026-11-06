"""Keep the targeted RF evaluation separate from the 16-workflow gate."""

from pathlib import Path

import pytest

from evals.structured_nlu.ai_heldout import load_reviewed_ai_heldout

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals/structured_nlu/data/ai_heldout/nlu-review-followup-reviewed.v1.json"
LEDGER = ROOT / "evals/structured_nlu/data/ai_heldout/nlu-review-followup-ledger.v1.json"
SCENARIOS = frozenset({"고객센터:a/s 접수", "교수님:면담 예약"})


def test_targeted_review_requires_explicit_scope() -> None:
    with pytest.raises(ValueError, match="all 16 detailed scenarios"):
        load_reviewed_ai_heldout(DATASET, LEDGER)

    reviewed = load_reviewed_ai_heldout(DATASET, LEDGER, expected_scenario_keys=SCENARIOS)
    assert len(reviewed.dataset.cases) == 12
    assert reviewed.scenario_counts == {
        "고객센터:a/s 접수": 6,
        "교수님:면담 예약": 6,
    }

    with pytest.raises(ValueError, match="required scope"):
        load_reviewed_ai_heldout(
            DATASET,
            LEDGER,
            expected_scenario_keys=frozenset({"고객센터:a/s 접수"}),
        )
