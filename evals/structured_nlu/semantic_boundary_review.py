"""Validate AI-written boundary drafts and gate model exposure on user review."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS

DEFAULT_DRAFT = (
    Path(__file__).resolve().parent
    / "data/exploratory/semantic-boundary-review-draft-2026-11-05.json"
)
FIELD_DRAFT = DEFAULT_DRAFT.with_name("semantic-boundary-field-draft-2026-11-05.json")
EXPECTED_IDS = tuple(f"SB{number:02}" for number in range(1, 13))
SUPPORT_DIRECTIONS = frozenset({"supported", "insufficient", "contradicted"})
REVIEW_LEDGER = DEFAULT_DRAFT.with_name("semantic-boundary-review-ledger-2026-11-05.json")
EXPOSURE_RECORD = DEFAULT_DRAFT.with_name("semantic-boundary-model-exposure-2026-11-05.json")


def load_review_draft(
    path: Path = DEFAULT_DRAFT,
    *,
    for_model_run: bool = False,
    review_ledger: Path = REVIEW_LEDGER,
    exposure_record: Path = EXPOSURE_RECORD,
    field_draft_path: Path = FIELD_DRAFT,
    source_bytes: bytes | None = None,
    field_draft_bytes: bytes | None = None,
    ledger_bytes: bytes | None = None,
) -> list[dict]:
    """Load a fixed-size draft; refuse model runs until exploratory acceptance."""
    source_bytes = path.read_bytes() if source_bytes is None else source_bytes
    source = json.loads(source_bytes)
    if (
        source.get("kind") != "ai_assisted_semantic_boundary_review_draft_v1"
        or source.get("provenance") != "ai_assisted_unreviewed"
        or source.get("not_official_test") is not True
        or source.get("model_exposure") != "not_run"
        or source.get("review_status")
        not in {
            "awaiting_user_review",
            "awaiting_full_field_review",
            "awaiting_negative_controls",
            "user_accepted_for_exploration",
        }
    ):
        raise ValueError("boundary draft provenance or review state invalid")
    if for_model_run and source["review_status"] != "user_accepted_for_exploration":
        raise ValueError("user exploratory review is required before model run")
    if for_model_run and exposure_record.exists():
        raise ValueError("boundary draft has already been exposed to the model")
    if for_model_run:
        if ledger_bytes is None and not review_ledger.is_file():
            raise ValueError("matching user review ledger is required before model run")
        ledger_bytes = review_ledger.read_bytes() if ledger_bytes is None else ledger_bytes
        field_draft_bytes = (
            field_draft_path.read_bytes() if field_draft_bytes is None else field_draft_bytes
        )
        ledger = json.loads(ledger_bytes)
        draft_sha256 = hashlib.sha256(source_bytes).hexdigest()
        if (
            ledger.get("kind") != "semantic_boundary_user_review_ledger_v1"
            or ledger.get("reviewed_for") != "exploratory_model_run_only"
            or ledger.get("draft_sha256") != draft_sha256
            or ledger.get("field_draft_sha256") != hashlib.sha256(field_draft_bytes).hexdigest()
            or ledger.get("accepted_case_ids") != list(EXPECTED_IDS)
            or not isinstance(ledger.get("review_note"), str)
            or not ledger["review_note"].strip()
        ):
            raise ValueError("matching user review ledger is required before model run")
    cases = source.get("cases")
    if not isinstance(cases, list) or tuple(case.get("id") for case in cases) != EXPECTED_IDS:
        raise ValueError("boundary draft requires exactly SB01 through SB12")
    if len({case.get("user_message") for case in cases}) != len(cases):
        raise ValueError("boundary draft messages must be unique")
    required = {
        "id",
        "scenario_key",
        "conversation_state",
        "user_message",
        "action_draft",
        "field",
        "candidate_value",
        "quote",
        "support_draft",
    }
    for case in cases:
        if set(case) != required:
            raise ValueError("boundary draft case shape invalid")
        contract = EVALUATION_CONTRACTS[case["scenario_key"]]
        if case["action_draft"] not in contract.allowed_actions_for_state(
            case["conversation_state"]
        ):
            raise ValueError("boundary draft action is not allowed in state")
        if case["field"] not in contract.field_names:
            raise ValueError("boundary draft field is outside scenario contract")
        options = dict(contract.field_options).get(case["field"])
        if options and case["candidate_value"] not in options:
            raise ValueError("boundary draft candidate is outside field options")
        message, quote = case["user_message"], case["quote"]
        if (
            not isinstance(message, str)
            or not message.strip()
            or not isinstance(quote, str)
            or not quote.strip()
            or message.count(quote) != 1
            or not isinstance(case["candidate_value"], str)
            or not case["candidate_value"].strip()
            or case["support_draft"] not in SUPPORT_DIRECTIONS
        ):
            raise ValueError("boundary draft sentence, quote or direction invalid")
    return cases


def load_field_draft(
    path: Path = FIELD_DRAFT,
    *,
    for_model_run: bool = False,
    source_bytes: bytes | None = None,
    sentences: list[dict] | None = None,
) -> list[dict]:
    """Check all fields against the live contract without treating drafts as gold."""
    source_bytes = path.read_bytes() if source_bytes is None else source_bytes
    source = json.loads(source_bytes)
    if (
        source.get("kind") != "ai_assisted_semantic_boundary_field_draft_v1"
        or source.get("provenance") != "ai_assisted_unreviewed"
        or source.get("not_official_test") is not True
        or source.get("model_exposure") != "not_run"
        or source.get("review_status")
        not in {
            "awaiting_user_field_review",
            "awaiting_negative_controls",
            "user_accepted_for_exploration",
        }
    ):
        raise ValueError("field draft provenance or review state invalid")
    if for_model_run and source["review_status"] != "user_accepted_for_exploration":
        raise ValueError("user field review is required before model run")
    if for_model_run and EXPOSURE_RECORD.exists():
        raise ValueError("boundary draft has already been exposed to the model")
    cases = source.get("cases")
    if not isinstance(cases, list) or tuple(case.get("id") for case in cases) != EXPECTED_IDS:
        raise ValueError("field draft requires exactly SB01 through SB12")
    if sentences is None:
        sentences = load_review_draft(
            for_model_run=for_model_run,
            field_draft_path=path,
            field_draft_bytes=source_bytes,
        )
    result = []
    for sentence, case in zip(sentences, cases, strict=True):
        if not isinstance(case, dict) or set(case) != {"id", "draft_fields"}:
            raise ValueError("field draft case shape invalid")
        contract = EVALUATION_CONTRACTS[sentence["scenario_key"]]
        fields = dict.fromkeys(contract.field_names)
        supplied = case["draft_fields"]
        if not isinstance(supplied, dict) or not set(supplied) <= set(fields):
            raise ValueError("field draft contains unknown field")
        if any(not isinstance(value, str) or not value.strip() for value in supplied.values()):
            raise ValueError("field draft contains blank or non-string value")
        fields.update(supplied)
        focus_value = fields[sentence["field"]]
        if sentence["support_draft"] == "supported":
            if focus_value != sentence["candidate_value"]:
                raise ValueError("field draft contradicts supported focus claim")
        elif focus_value is not None:
            raise ValueError("field draft contradicts blank focus claim")
        intent = (
            contract.workflow_spec.intent
            if contract.workflow_spec
            else next(iter(contract.allowed_intents))
        )
        contract.validate_prediction(
            intent=intent,
            fields=fields,
            user_action=sentence["action_draft"],
            change_field=None,
            conversation_state=sentence["conversation_state"],
            current_fields=dict.fromkeys(contract.field_names)
            if contract.uses_current_fields
            else None,
        )
        result.append({"id": case["id"], "fields": fields})
    return result
