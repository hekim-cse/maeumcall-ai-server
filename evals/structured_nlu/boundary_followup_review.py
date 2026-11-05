"""Validate the new AI development draft before any model exposure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS

DEFAULT_DRAFT = (
    Path(__file__).resolve().parent
    / "data/exploratory/boundary-followup-review-draft-2026-11-05.json"
)
REVIEW_LEDGER = DEFAULT_DRAFT.with_name("boundary-followup-review-ledger-2026-11-05.json")
EXPOSURE_RECORD = DEFAULT_DRAFT.with_name("boundary-followup-model-exposure-2026-11-05.json")
EXPECTED_IDS = tuple(f"BF{index:02}" for index in range(1, 11))
GROUP_BY_ID = {
    **{case_id: "workflow_field_presence" for case_id in EXPECTED_IDS[:6]},
    **{case_id: "date_normalization" for case_id in EXPECTED_IDS[6:]},
}


def load_followup_draft(
    path: Path = DEFAULT_DRAFT,
    *,
    for_model_run: bool = False,
    review_ledger: Path = REVIEW_LEDGER,
    exposure_record: Path = EXPOSURE_RECORD,
    source_bytes: bytes | None = None,
    ledger_bytes: bytes | None = None,
) -> list[dict]:
    """Check provenance, user approval, live contracts, and frozen focus labels."""
    source_bytes = path.read_bytes() if source_bytes is None else source_bytes
    source = json.loads(source_bytes)
    if (
        source.get("kind") != "ai_assisted_boundary_followup_review_draft_v1"
        or source.get("provenance") != "ai_assisted_unreviewed"
        or source.get("not_official_test") is not True
        or source.get("model_exposure") != "not_run"
        or source.get("reference_date") != "2026-11-05"
        or source.get("reference_timezone") != "Asia/Seoul"
        or source.get("review_status")
        not in {"awaiting_user_review", "user_accepted_for_exploration"}
    ):
        raise ValueError("followup draft provenance, date, or review state invalid")
    if for_model_run:
        if source["review_status"] != "user_accepted_for_exploration":
            raise ValueError("user exploratory review is required before model run")
        if exposure_record.exists():
            raise ValueError("followup draft has already been exposed to the model")
        if ledger_bytes is None and not review_ledger.is_file():
            raise ValueError("matching user review ledger is required before model run")
        ledger_bytes = review_ledger.read_bytes() if ledger_bytes is None else ledger_bytes
        ledger = json.loads(ledger_bytes)
        if (
            ledger.get("kind") != "boundary_followup_user_review_ledger_v1"
            or ledger.get("reviewed_for") != "exploratory_model_run_only"
            or ledger.get("draft_sha256") != hashlib.sha256(source_bytes).hexdigest()
            or ledger.get("accepted_case_ids") != list(EXPECTED_IDS)
            or not isinstance(ledger.get("review_note"), str)
            or not ledger["review_note"].strip()
        ):
            raise ValueError("matching user review ledger is required before model run")
    cases = source.get("cases")
    if (
        not isinstance(cases, list)
        or any(not isinstance(case, dict) for case in cases)
        or tuple(case.get("id") for case in cases) != EXPECTED_IDS
    ):
        raise ValueError("followup draft requires exactly BF01 through BF10")
    expected_keys = {
        "id",
        "group",
        "scenario_key",
        "conversation_state",
        "user_message",
        "action_draft",
        "field_draft",
        "focus_field",
        "focus_accepted_values",
    }
    for case in cases:
        if not isinstance(case, dict) or set(case) != expected_keys:
            raise ValueError("followup draft case shape invalid")
        if case["group"] != GROUP_BY_ID[case["id"]]:
            raise ValueError("followup draft group invalid")
        message = case["user_message"]
        if not isinstance(message, str) or not message.strip():
            raise ValueError("followup draft message must be nonblank")
        contract = EVALUATION_CONTRACTS[case["scenario_key"]]
        if case["action_draft"] not in contract.allowed_actions_for_state(
            case["conversation_state"]
        ):
            raise ValueError("followup draft action is outside live state")
        fields = dict.fromkeys(contract.field_names)
        supplied = case["field_draft"]
        if not isinstance(supplied, dict) or not set(supplied) <= set(fields):
            raise ValueError("followup draft contains unknown field")
        if any(not isinstance(value, str) or not value.strip() for value in supplied.values()):
            raise ValueError("followup draft contains blank or non-string field")
        fields.update(supplied)
        focus = case["focus_field"]
        if focus not in fields:
            raise ValueError("followup draft focus is outside live contract")
        accepted = case["focus_accepted_values"]
        if fields[focus] is None:
            if accepted is not None:
                raise ValueError("blank followup focus requires null accepted values")
        elif (
            not isinstance(accepted, list)
            or not accepted
            or any(not isinstance(value, str) or not value.strip() for value in accepted)
            or len(set(accepted)) != len(accepted)
            or fields[focus] not in accepted
        ):
            raise ValueError("nonblank followup focus requires unique accepted values")
        intent = contract.workflow_spec.intent if contract.workflow_spec else "reservation"
        contract.validate_prediction(
            intent=intent,
            fields=fields,
            user_action=case["action_draft"],
            change_field=None,
            conversation_state=case["conversation_state"],
            current_fields=dict.fromkeys(contract.field_names)
            if contract.uses_current_fields
            else None,
        )
    if len({case["user_message"] for case in cases}) != len(cases):
        raise ValueError("followup draft messages must be unique")
    return cases
