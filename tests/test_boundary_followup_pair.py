"""Verify reviewed labels and bounded observations in the followup runner."""

import json

import pytest

from evals.structured_nlu.boundary_followup_review import load_followup_draft
from scripts.probe_gguf_boundary_followup_pair import _runner_case, _safe_observation

pytestmark = pytest.mark.unit


def test_date_accepted_values_are_frozen_in_runner_case():
    draft = load_followup_draft()[7]
    case = _runner_case(draft)
    assert case["labels"]["fields"]["date"] == {
        "accepted_values": ["2026년 12월 첫째 주 금요일", "2026년 12월 4일", "2026-12-04"]
    }
    assert case["labels"]["fields"]["start_time"] == {"accepted_values": ["오후 3시"]}


def test_contract_failure_never_gets_draft_credit():
    draft = load_followup_draft()[0]
    failure = {"last_error_code": "action_missing_required_field"}
    observation = _safe_observation(
        draft,
        "candidate",
        1,
        {
            "contract_valid": False,
            "elapsed_seconds": 0.1,
            "attempts": [
                {"output_shape": {"present_field_names": [], "user_action": "provide_details"}}
            ],
            "failure": failure,
        },
    )
    assert observation["action_matches_draft"] is False
    assert observation["focus_field_matches_draft"] is False
    assert observation["all_fields_and_action_match_draft"] is False
    assert observation["focus_field_present_in_last_attempt"] is False
    assert observation["failure"] == failure
    assert "user_message" not in json.dumps(observation, ensure_ascii=False)


def test_date_focus_presence_is_separate_from_label_match():
    draft = load_followup_draft()[8]
    observation = _safe_observation(
        draft,
        "baseline",
        1,
        {
            "contract_valid": True,
            "draft_label_mismatch_fields": ["date"],
            "elapsed_seconds": 0.1,
            "attempts": [{"output_shape": {"present_field_names": ["date"]}}],
        },
    )
    assert observation["focus_field_present_in_last_attempt"] is True
    assert observation["focus_field_matches_draft"] is False
    assert "date_value" not in observation
