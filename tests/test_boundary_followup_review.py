"""Keep new AI development cases behind review and live-contract gates."""

import hashlib
import json

import pytest

from evals.structured_nlu.boundary_followup_review import (
    DEFAULT_DRAFT,
    load_followup_draft,
)

pytestmark = pytest.mark.unit


def test_unreviewed_draft_matches_live_contract_but_cannot_run(tmp_path):
    cases = load_followup_draft()
    assert [case["id"] for case in cases] == [f"BF{index:02}" for index in range(1, 11)]
    source = json.loads(DEFAULT_DRAFT.read_text())
    source["review_status"] = "awaiting_user_review"
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="user exploratory review"):
        load_followup_draft(path, for_model_run=True)


def test_review_ledger_must_match_exact_input_bytes(tmp_path):
    source = json.loads(DEFAULT_DRAFT.read_text())
    source["review_status"] = "user_accepted_for_exploration"
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(source))
    ledger_path = tmp_path / "ledger.json"
    exposure_path = tmp_path / "exposure.json"
    with pytest.raises(ValueError, match="matching user review ledger"):
        load_followup_draft(
            path, for_model_run=True, review_ledger=ledger_path, exposure_record=exposure_path
        )
    ledger = {
        "kind": "boundary_followup_user_review_ledger_v1",
        "reviewed_for": "exploratory_model_run_only",
        "draft_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "accepted_case_ids": [f"BF{index:02}" for index in range(1, 11)],
        "review_note": "user accepted exploratory development cases",
    }
    ledger_path.write_text(json.dumps(ledger))
    assert (
        len(
            load_followup_draft(
                path, for_model_run=True, review_ledger=ledger_path, exposure_record=exposure_path
            )
        )
        == 10
    )
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="matching user review ledger"):
        load_followup_draft(
            path, for_model_run=True, review_ledger=ledger_path, exposure_record=exposure_path
        )
    path.write_text(json.dumps(source))
    exposure_path.write_text("{}")
    with pytest.raises(ValueError, match="already been exposed"):
        load_followup_draft(
            path, for_model_run=True, review_ledger=ledger_path, exposure_record=exposure_path
        )


@pytest.mark.parametrize(
    ("case_index", "mutation", "message"),
    [
        (0, {"field_draft": {"unknown_field": "value"}}, "unknown field"),
        (0, {"field_draft": {"issue_type": "   "}}, "blank or non-string field"),
        (
            0,
            {
                "field_draft": {"issue_type": "invalid_enum"},
                "focus_accepted_values": ["invalid_enum"],
            },
            "prediction issue_type is not allowed",
        ),
        (6, {"focus_accepted_values": ["2026-12-05"]}, "unique accepted values"),
        (9, {"focus_accepted_values": ["2026-12-04"]}, "requires null accepted values"),
    ],
)
def test_invalid_fields_and_focus_values_are_rejected(tmp_path, case_index, mutation, message):
    source = json.loads(DEFAULT_DRAFT.read_text())
    source["cases"][case_index].update(mutation)
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match=message):
        load_followup_draft(path)
