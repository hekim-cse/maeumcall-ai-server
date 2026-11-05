"""Keep unreviewed AI boundary cases out of model and official test paths."""

import hashlib
import json

import pytest

import evals.structured_nlu.semantic_boundary_review as review_module
from evals.structured_nlu.semantic_boundary_review import (
    DEFAULT_DRAFT,
    FIELD_DRAFT,
    load_field_draft,
    load_review_draft,
)
from scripts.probe_gguf_semantic_boundary_pair import (
    EXPECTED_IMAGE_DIGEST,
    EXPECTED_MODEL_SHA256,
    _case_for_runner,
    _safe_observation,
    verify_expected_runtime,
)
from scripts.probe_gguf_structured_nlu import with_extra_instruction

pytestmark = pytest.mark.unit


def test_unreviewed_draft_is_valid_but_not_runnable(tmp_path):
    assert len(load_review_draft()) == 12
    assert len(load_field_draft()) == 12
    sentence_source = json.loads(DEFAULT_DRAFT.read_text())
    sentence_source["review_status"] = "awaiting_user_review"
    sentence_path = tmp_path / "sentences.json"
    sentence_path.write_text(json.dumps(sentence_source))
    with pytest.raises(ValueError, match="user exploratory review"):
        load_review_draft(sentence_path, for_model_run=True)
    field_source = json.loads(FIELD_DRAFT.read_text())
    field_source["review_status"] = "awaiting_user_field_review"
    field_path = tmp_path / "fields.json"
    field_path.write_text(json.dumps(field_source))
    with pytest.raises(ValueError, match="user field review"):
        load_field_draft(field_path, for_model_run=True)


def test_official_or_exposed_data_cannot_be_loaded(tmp_path):
    source = json.loads(DEFAULT_DRAFT.read_text())
    path = tmp_path / "draft.json"
    for key, value in (("not_official_test", False), ("model_exposure", "exploratory_exposed")):
        changed = source | {key: value}
        path.write_text(json.dumps(changed))
        with pytest.raises(ValueError, match="provenance or review state"):
            load_review_draft(path)


def test_quote_and_contract_field_are_checked(tmp_path):
    source = json.loads(DEFAULT_DRAFT.read_text())
    path = tmp_path / "draft.json"
    source["cases"][0]["quote"] = "문장에 없는 인용"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="sentence, quote or direction"):
        load_review_draft(path)


def test_model_gate_requires_matching_user_review_ledger(tmp_path):
    source = json.loads(DEFAULT_DRAFT.read_text())
    source["review_status"] = "user_accepted_for_exploration"
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(source))
    ledger_path = tmp_path / "ledger.json"
    exposure_path = tmp_path / "exposure.json"
    with pytest.raises(ValueError, match="matching user review ledger"):
        load_review_draft(
            path, for_model_run=True, review_ledger=ledger_path, exposure_record=exposure_path
        )
    ledger = {
        "kind": "semantic_boundary_user_review_ledger_v1",
        "reviewed_for": "exploratory_model_run_only",
        "draft_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "field_draft_sha256": hashlib.sha256(FIELD_DRAFT.read_bytes()).hexdigest(),
        "accepted_case_ids": [f"SB{index:02}" for index in range(1, 13)],
        "review_note": "user accepted exploratory cases",
    }
    ledger_path.write_text(json.dumps(ledger))
    assert (
        len(
            load_review_draft(
                path,
                for_model_run=True,
                review_ledger=ledger_path,
                exposure_record=exposure_path,
            )
        )
        == 12
    )
    exposure_path.write_text("{}")
    with pytest.raises(ValueError, match="already been exposed"):
        load_review_draft(
            path, for_model_run=True, review_ledger=ledger_path, exposure_record=exposure_path
        )
    exposure_path.unlink()
    ledger["draft_sha256"] = "0" * 64
    ledger_path.write_text(json.dumps(ledger))
    with pytest.raises(ValueError, match="matching user review ledger"):
        load_review_draft(
            path, for_model_run=True, review_ledger=ledger_path, exposure_record=exposure_path
        )


def test_field_draft_respects_live_contract(tmp_path):
    source = json.loads(FIELD_DRAFT.read_text())
    source["cases"][0]["draft_fields"]["issue_type"] = "not_an_option"
    path = tmp_path / "fields.json"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="issue_type is not allowed"):
        load_field_draft(path)


@pytest.mark.parametrize("bad_fields", [{"unknown_field": "value"}, {"issue_type": "   "}])
def test_field_draft_rejects_unknown_or_blank_values(tmp_path, bad_fields):
    source = json.loads(FIELD_DRAFT.read_text())
    source["cases"][0]["draft_fields"].update(bad_fields)
    path = tmp_path / "fields.json"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="unknown field|blank or non-string value"):
        load_field_draft(path)


def test_field_draft_cannot_contradict_focus_direction(tmp_path, monkeypatch):
    source = json.loads(FIELD_DRAFT.read_text())
    path = tmp_path / "fields.json"
    sentences = load_review_draft()
    sentences[0] = {**sentences[0], "support_draft": "insufficient"}
    monkeypatch.setattr(review_module, "load_review_draft", lambda **_kwargs: sentences)
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="blank focus claim"):
        load_field_draft(path)
    sentences[0] = {**sentences[0], "support_draft": "supported"}
    source["cases"][0]["draft_fields"].pop("resolution_preference")
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="supported focus claim"):
        load_field_draft(path)


def test_runner_labels_keep_focus_separate_from_other_fields():
    sentence = load_review_draft()[1]
    draft = load_field_draft()[1]
    case = _case_for_runner(sentence, draft)
    assert case["labels"]["fields"]["resolution_preference"] == {"accepted_values": ["refund"]}
    assert case["labels"]["fields"]["issue_type"] == {"accepted_values": ["wrong_item"]}
    observation = _safe_observation(
        sentence,
        "candidate",
        1,
        {
            "contract_valid": True,
            "draft_label_mismatch_fields": ["resolution_preference"],
            "elapsed_seconds": 0.1,
            "attempts": [],
        },
    )
    assert observation["action_matches_draft"] is True
    assert observation["focus_field_matches_draft"] is False
    assert observation["all_fields_and_action_match_draft"] is False


def test_failed_contract_observation_preserves_failure_without_draft_credit():
    sentence = load_review_draft()[0]
    failure = {"last_error_code": "action_missing_required_field"}
    observation = _safe_observation(
        sentence,
        "baseline",
        1,
        {
            "contract_valid": False,
            "failure": failure,
            "elapsed_seconds": 0.1,
            "attempts": [],
        },
    )
    assert observation["contract_valid"] is False
    assert observation["action_matches_draft"] is False
    assert observation["focus_field_matches_draft"] is False
    assert observation["all_fields_and_action_match_draft"] is False
    assert observation["failure"] == failure


def test_runner_rejects_unfrozen_model_or_server_image():
    runtime = {
        "model_sha256": EXPECTED_MODEL_SHA256,
        "server_image_digest": EXPECTED_IMAGE_DIGEST,
    }
    verify_expected_runtime(runtime)
    with pytest.raises(ValueError, match="mounted model differs"):
        verify_expected_runtime(runtime | {"model_sha256": "0" * 64})
    with pytest.raises(ValueError, match="server image differs"):
        verify_expected_runtime(runtime | {"server_image_digest": "sha256:" + "0" * 64})


def test_candidate_instruction_stays_on_original_user_message_during_retry():
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "original"},
        {"role": "user", "content": "retry feedback"},
    ]
    augmented = with_extra_instruction(messages, "policy")
    assert augmented[1]["content"] == "original\npolicy"
    assert augmented[2]["content"] == "retry feedback"
    assert messages[1]["content"] == "original"
