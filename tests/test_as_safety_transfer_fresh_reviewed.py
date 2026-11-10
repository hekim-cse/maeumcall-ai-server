"""Guard owner-reviewed TX input before its first model exposure."""

import json
from pathlib import Path

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
        assert set(case) == {"id", "user_message", "expected_route", "expected_relation"}
        clauses = split_clauses(case["user_message"])
        assert len(clauses) == 2
        relation = validate_relation(json.dumps(case["expected_relation"]), len(clauses))
        assert route_relation(relation) == case["expected_route"]
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
