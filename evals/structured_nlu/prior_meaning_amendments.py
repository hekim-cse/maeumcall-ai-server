"""Apply later user decisions without rewriting inputs of historical probes."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from scripts.action_field_dev_cases import DEFAULT_SOURCE
from scripts.action_field_dev_cases import load_cases as load_dev_cases
from scripts.fresh_scope_ai_cases import (
    FIELD_DRAFT,
    SENTENCES,
)
from scripts.fresh_scope_ai_cases import (
    load_cases as load_fresh_cases,
)

AMENDMENTS = (
    Path(__file__).resolve().parent / "data/exploratory/prior-meaning-amendments-2026-11-05.json"
)
INPUTS = {
    "fresh_sentences": SENTENCES,
    "fresh_field_draft": FIELD_DRAFT,
    "development_draft": DEFAULT_SOURCE,
}


def load_amended_development_cases(path: Path = AMENDMENTS) -> list[dict]:
    """Return copies with the new exploratory directions, never mutate old sources."""
    source = json.loads(path.read_text(encoding="utf-8"))
    if (
        source.get("kind") != "exploratory_prior_meaning_amendments_v1"
        or source.get("provenance") != "user_revised_direction_for_ai_assisted_development_cases"
        or source.get("not_official_test") is not True
        or source.get("applies_to") != "future_exploration_only"
        or source.get("historical_reports_unchanged") is not True
    ):
        raise ValueError("meaning amendments must remain exploratory")
    observed_hashes = {
        name: hashlib.sha256(input_path.read_bytes()).hexdigest()
        for name, input_path in INPUTS.items()
    }
    if source.get("source_sha256") != observed_hashes:
        raise ValueError("historical case sources differ from amendment record")
    cases = deepcopy([*load_fresh_cases(), *load_dev_cases()])
    by_id = {case["id"]: case for case in cases}
    if len(by_id) != len(cases):
        raise ValueError("development case IDs must be unique")
    amendments = source.get("amendments")
    if not isinstance(amendments, list) or {
        (item.get("case_id"), item.get("field")) for item in amendments
    } != {("D05", "resolution_preference"), ("F23", "issuance_channel")}:
        raise ValueError("unexpected meaning amendments")
    for item in amendments:
        case = by_id[item["case_id"]]
        field = item["field"]
        if case["labels"]["fields"][field] is not item["old_value"]:
            raise ValueError("old exploratory value differs from amendment")
        value = item["new_value"]
        contract = EVALUATION_CONTRACTS[case["scenario_key"]]
        if value not in dict(contract.field_options).get(field, frozenset()):
            raise ValueError("new exploratory value is outside live field options")
        case["labels"]["fields"][field] = {"accepted_values": [value]}
    return cases
