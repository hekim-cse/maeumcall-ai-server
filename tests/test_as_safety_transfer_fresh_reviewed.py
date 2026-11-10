"""Guard owner-reviewed TX input before its first model exposure."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.probe_as_safety_clause_index import split_clauses
from scripts.probe_as_safety_relation import route_relation, validate_relation

DATA = Path("evals/structured_nlu/data/ai_heldout")
TX = DATA / "as-safety-transfer-fresh-reviewed.v1.json"
PREVIOUS = (
    DATA / "as-safety-relation-fresh-reviewed.v1.json",
    DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
)
DIRECT = "safety_action_required"
CONFIRM = "confirming_safety_status"
NORMAL = "collecting_service_request"
EXPECTED = {
    "TX01": ("current", "observed", DIRECT),
    "TX02": ("other", "observed", NORMAL),
    "TX03": ("current", "observed", DIRECT),
    "TX04": ("other", "observed", NORMAL),
    "TX05": ("current", "observed", DIRECT),
    "TX06": ("other", "observed", NORMAL),
    "TX07": ("current", "observed", DIRECT),
    "TX08": ("other", "observed", NORMAL),
    "TX09": ("unknown", "observed", CONFIRM),
    "TX10": ("unknown", "observed", CONFIRM),
    "TX11": ("unknown", "observed", CONFIRM),
    "TX12": ("current", "uncertain", CONFIRM),
    "TX13": ("other", "nonoccurring", NORMAL),
    "TX14": ("current", "nonoccurring", NORMAL),
    "TX15": ("current", "nonoccurring", NORMAL),
    "TX16": ("current", "nonoccurring", NORMAL),
}


def validate_tx_case(case: dict) -> None:
    if set(case) != {"id", "user_message", "expected_route", "expected_relation"}:
        raise ValueError("TX fields differ")
    clauses = split_clauses(case["user_message"])
    if len(clauses) != 2:
        raise ValueError(f"{case['id']}: TX must have two source clauses, got {clauses}")
    relation = validate_relation(json.dumps(case["expected_relation"]), len(clauses))
    if case["id"] not in EXPECTED:
        raise ValueError("unknown TX id")
    target, event, route = EXPECTED[case["id"]]
    if relation != {
        "product_index": 1,
        "hazard_index": 2,
        "target_relation": target,
        "event_status": event,
    }:
        raise ValueError("TX relation differs from owner-reviewed label")
    if case["expected_route"] != route or route_relation(relation) != route:
        raise ValueError("TX route differs from owner-reviewed label")


def test_reviewed_tx_contract_and_prior_exposure_boundary():
    payload = json.loads(TX.read_text(encoding="utf-8"))
    assert payload["kind"] == "as_safety_transfer_fresh_ai_reviewed_v1"
    assert payload["provenance"] == "ai_authored"
    assert payload["review_status"] == "owner_approved_for_exploration"
    assert payload["model_exposure_at_freeze"] == "none"
    cases = payload["cases"]
    assert [case["id"] for case in cases] == [f"TX{number:02}" for number in range(1, 17)]
    previous_messages = {
        case["user_message"]
        for path in PREVIOUS
        for case in json.loads(path.read_text(encoding="utf-8"))["cases"]
    }
    assert not {case["user_message"] for case in cases} & previous_messages
    assert len({case["user_message"] for case in cases}) == 16
    for index, case in enumerate(cases):
        validate_tx_case(case)
        if index < 8:
            assert case["expected_route"] == (DIRECT if index % 2 == 0 else NORMAL)
        elif index < 12:
            assert case["expected_route"] == CONFIRM
        else:
            assert case["expected_route"] == NORMAL
    for first in range(0, 8, 2):
        assert (
            split_clauses(cases[first]["user_message"])[0]
            == split_clauses(cases[first + 1]["user_message"])[0]
        )


@pytest.mark.parametrize(
    ("change", "value"),
    [
        (("user_message",), " "),
        (("expected_route",), DIRECT),
        (("expected_relation", "unknown_field"), "value"),
        (("expected_relation", "product_index"), 3),
        (("expected_relation", "target_relation"), "current"),
    ],
)
def test_reviewed_tx_rejects_changed_or_invalid_fields(change, value):
    case = deepcopy(json.loads(TX.read_text(encoding="utf-8"))["cases"][1])
    field = case
    for key in change[:-1]:
        field = field[key]
    field[change[-1]] = value
    with pytest.raises(ValueError):
        validate_tx_case(case)
