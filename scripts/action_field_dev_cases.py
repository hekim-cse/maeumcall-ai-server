"""Load AI-assisted development cases without promoting them to official test data."""

from __future__ import annotations

import json
from pathlib import Path

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS

DEFAULT_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "evals/structured_nlu/data/exploratory/action-field-dev-2026-11-04.json"
)
EXPECTED_IDS = [f"D{number:02}" for number in range(1, 9)]


def load_cases(path: Path = DEFAULT_SOURCE) -> list[dict]:
    source = json.loads(path.read_text())
    if (
        source.get("kind") != "exploratory_action_field_dev_cases_v1"
        or source.get("provenance") != "ai_assisted_unreviewed"
        or source.get("reviewed_scope")
        != "user_reviewed_sentence_and_action_field_meaning_on_2026-11-04"
        or source.get("normalized_value_status") != "ai_draft_unreviewed"
        or source.get("not_official_test") is not True
    ):
        raise ValueError("source must remain AI-assisted exploratory development data")
    drafts = source.get("cases")
    if not isinstance(drafts, list) or [draft.get("id") for draft in drafts] != EXPECTED_IDS:
        raise ValueError("development case IDs must be D01 through D08")
    messages = [draft.get("user_message") for draft in drafts]
    if any(not isinstance(message, str) or not message.strip() for message in messages):
        raise ValueError("development user messages must be nonempty")
    if len(set(messages)) != len(messages):
        raise ValueError("development user messages must be unique")

    cases = []
    for draft in drafts:
        contract = EVALUATION_CONTRACTS[draft["scenario_key"]]
        spec = contract.workflow_spec
        if spec is None:
            raise ValueError("development split cases must use service workflows")
        current_fields = dict.fromkeys(spec.field_keys)
        fields = dict.fromkeys(spec.field_keys)
        supplied = draft["draft_fields"]
        if not isinstance(supplied, dict) or not set(supplied) <= set(fields):
            raise ValueError(f"unknown draft field in {draft['id']}")
        fields.update(supplied)
        contract.validate_prediction(
            intent=spec.intent,
            fields=fields,
            user_action=draft["user_action"],
            change_field=None,
            conversation_state=spec.collecting_state,
            current_fields=current_fields,
        )
        cases.append(
            {
                "id": draft["id"],
                "scenario_key": draft["scenario_key"],
                "conversation_state": spec.collecting_state,
                "current_fields": current_fields,
                "offered_alternative_times": [],
                "user_message": draft["user_message"],
                "labels": {
                    "intent": spec.intent,
                    "user_action": draft["user_action"],
                    "change_field": None,
                    "fields": {
                        name: None if value is None else {"accepted_values": [value]}
                        for name, value in fields.items()
                    },
                },
            }
        )
    return cases
