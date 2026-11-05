"""Keep later exploratory labels versioned and original run inputs intact."""

import json

import pytest

from evals.structured_nlu.prior_meaning_amendments import (
    AMENDMENTS,
    load_amended_development_cases,
)
from scripts.action_field_dev_cases import load_cases as load_dev_cases
from scripts.fresh_scope_ai_cases import load_cases as load_fresh_cases

pytestmark = pytest.mark.unit


def test_later_user_directions_do_not_mutate_historical_inputs():
    amended = {case["id"]: case for case in load_amended_development_cases()}
    original = {case["id"]: case for case in [*load_fresh_cases(), *load_dev_cases()]}
    assert original["D05"]["labels"]["fields"]["resolution_preference"] is None
    assert original["F23"]["labels"]["fields"]["issuance_channel"] is None
    assert amended["D05"]["labels"]["fields"]["resolution_preference"] == {
        "accepted_values": ["refund"]
    }
    assert amended["F23"]["labels"]["fields"]["issuance_channel"] == {
        "accepted_values": ["government24"]
    }


def test_amendment_requires_source_fingerprint(tmp_path):
    source = json.loads(AMENDMENTS.read_text())
    source["source_sha256"]["development_draft"] = "0" * 64
    path = tmp_path / "amendments.json"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="sources differ"):
        load_amended_development_cases(path)


def test_amendment_rejects_value_outside_contract(tmp_path):
    source = json.loads(AMENDMENTS.read_text())
    source["amendments"][0]["new_value"] = "not_an_option"
    path = tmp_path / "amendments.json"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="outside live field options"):
        load_amended_development_cases(path)
