"""Reject review-table ambiguities before a corpus can be sealed."""

from __future__ import annotations

import pytest

from scripts import materialize_nlu_scope_dataset as materialize


def test_duplicate_review_id_is_rejected(tmp_path) -> None:
    review = tmp_path / "duplicate.md"
    review.write_text("| NS01 | first |\n| NS01 | second |\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate ID"):
        materialize._table_rows(review)


def test_reviewed_workflow_must_match_template_scenario(tmp_path, monkeypatch) -> None:
    review = tmp_path / "wrong-workflow.md"
    review.write_text(
        materialize.REVIEW.read_text(encoding="utf-8").replace(
            "| NS30 | 스터디룸 예약 |", "| NS30 | 식당 예약 |"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize, "REVIEW", review)
    monkeypatch.setattr(materialize, "OUTPUT", tmp_path / "dataset.json")
    monkeypatch.setattr(materialize, "LEDGER", tmp_path / "ledger.json")

    with pytest.raises(ValueError, match="scenario differs"):
        materialize.main()
