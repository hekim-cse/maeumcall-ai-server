"""Keep the targeted RF evaluation separate from the 16-workflow gate."""

import json
from pathlib import Path

import pytest

from evals.structured_nlu.ai_heldout import load_reviewed_ai_heldout
from scripts import materialize_nlu_review_followup_dataset as materializer
from scripts.run_nlu_scope_revision_pair import _protocol_scope
from scripts.verify_nlu_scope_revision_pair import verify

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals/structured_nlu/data/ai_heldout/nlu-review-followup-reviewed.v1.json"
LEDGER = ROOT / "evals/structured_nlu/data/ai_heldout/nlu-review-followup-ledger.v1.json"
SCENARIOS = frozenset({"고객센터:a/s 접수", "교수님:면담 예약"})
PROTOCOL = (
    ROOT / "evals/structured_nlu/data/ai_heldout/nlu-review-followup-code-pair-protocol.v1.json"
)
RESULT = ROOT / "evals/structured_nlu/results/nlu-review-followup-code-pair-v1.json"


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


def test_materializer_recreates_exact_bytes_after_partial_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / DATASET.name
    ledger = tmp_path / LEDGER.name
    monkeypatch.setattr(materializer, "OUTPUT", output)
    monkeypatch.setattr(materializer, "LEDGER", ledger)
    materializer.main()
    assert output.read_bytes() == DATASET.read_bytes()
    assert ledger.read_bytes() == LEDGER.read_bytes()

    ledger.unlink()
    materializer.main()
    assert ledger.read_bytes() == LEDGER.read_bytes()

    with pytest.raises(ValueError, match="never overwrite"):
        materializer.main()


def test_targeted_protocol_claim_is_required_before_model_run() -> None:
    frozen = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert _protocol_scope(frozen) == (
        SCENARIOS,
        "single_owner_reviewed_ai_authored_12_case_review_followup",
    )
    frozen.pop("result_claim_scope")
    with pytest.raises(ValueError, match="explicit targeted result_claim_scope"):
        _protocol_scope(frozen)

    legacy = json.loads(
        (
            ROOT / "evals/structured_nlu/data/ai_heldout/nlu-scope-code-pair-protocol.v3.json"
        ).read_text(encoding="utf-8")
    )
    legacy["scenario_keys"] = sorted(SCENARIOS)
    with pytest.raises(ValueError, match="revision 3 cannot declare"):
        _protocol_scope(legacy)


def test_targeted_result_and_legacy_result_verify() -> None:
    assert verify(DATASET, LEDGER, PROTOCOL, RESULT)["cases"] == 12
    data_dir = ROOT / "evals/structured_nlu/data/ai_heldout"
    result_dir = ROOT / "evals/structured_nlu/results"
    assert (
        verify(
            data_dir / "nlu-scope-reviewed.v2.json",
            data_dir / "nlu-scope-review-ledger.v2.json",
            data_dir / "nlu-scope-code-pair-protocol.v3.json",
            result_dir / "nlu-scope-code-pair-v3.json",
        )["cases"]
        == 32
    )
