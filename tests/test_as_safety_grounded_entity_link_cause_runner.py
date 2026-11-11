"""No-model checks for the cause-decomposition journal."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from scripts import run_as_safety_grounded_entity_link_cause_diagnostic as runner
from scripts.probe_as_safety_clause_index import split_clauses

MESSAGE = "접수할 노트북이 켜지지 않습니다. 친구 태블릿의 충전기에서 연기가 납니다."
CASE = {
    "id": "SYN01",
    "user_message": MESSAGE,
    "expected_relation": {"product_index": 1, "event_status": "observed"},
}
SPAN = {"target_mention": "노트북"}
OWNER = {"clause_index": 2, "mention": "친구 태블릿의 충전기"}


def _response(link: str, evidence: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(
        content=json.dumps({"entity_link": link, "evidence": evidence}, ensure_ascii=False),
        finish_reason="stop",
    )


@pytest.mark.parametrize(
    ("link", "evidence", "status", "effective"),
    [
        ("unresolved", [], "model_abstained", "unresolved"),
        ("distinct_item", [], "rejected_missing_evidence", "unresolved"),
        (
            "distinct_item",
            [{"clause_index": 1, "quote": split_clauses(MESSAGE)[0]}],
            "rejected_missing_owner",
            "unresolved",
        ),
        (
            "distinct_item",
            [
                {"clause_index": i, "quote": clause}
                for i, clause in enumerate(split_clauses(MESSAGE), 1)
            ],
            "accepted",
            "distinct_item",
        ),
    ],
)
def test_model_choice_and_anchor_fallback_remain_separate(
    monkeypatch, link, evidence, status, effective
):
    monkeypatch.setattr(runner, "post_completion", lambda *_args: _response(link, evidence))
    row = runner._call(CASE, SPAN, OWNER, object())
    assert (row["model_entity_link"], row["anchor_status"], row["entity_link"]) == (
        link,
        status,
        effective,
    )
    assert MESSAGE not in json.dumps(row, ensure_ascii=False)
    assert all("quote" not in span or "quote_sha256" in span for span in row["evidence_spans"])


def test_contract_error_has_no_model_choice(monkeypatch):
    monkeypatch.setattr(
        runner,
        "post_completion",
        lambda *_args: SimpleNamespace(content="{", finish_reason="stop"),
    )
    row = runner._call(CASE, SPAN, OWNER, object())
    assert row["model_entity_link"] is None
    assert row["anchor_status"] == "not_evaluated"
    assert row["entity_link"] is None
    assert (row["error_stage"], row["error_code"]) == ("contract", "invalid_json")
