"""No-model runner checks for the symmetric A/S relation candidate."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from scripts import run_as_safety_symmetric_link_development as runner

MESSAGE = "이 기기의 알림 버튼을 수리하려고 합니다. 옆 장비의 전원선 피복이 벗겨졌습니다."
CASE = {
    "id": "SYN01",
    "user_message": MESSAGE,
    "expected_relation": {"product_index": 1, "event_status": "observed"},
}
SPAN = {"target_mention": "이 기기"}
OWNER = {"clause_index": 2, "mention": "옆 장비의 전원선"}


def _response(same: str, distinct: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=json.dumps({"same_or_part": same, "distinct_item": distinct}),
        finish_reason="stop",
    )


@pytest.mark.parametrize(
    ("same", "distinct", "link", "relation", "route"),
    [
        ("yes", "no", "same_or_part", "current", "safety_action_required"),
        ("no", "yes", "distinct_item", "other", "collecting_service_request"),
        ("yes", "yes", "unresolved", "unknown", "confirming_safety_status"),
        ("uncertain", "uncertain", "unresolved", "unknown", "confirming_safety_status"),
    ],
)
def test_single_call_keeps_both_answers_and_route(
    monkeypatch, same, distinct, link, relation, route
):
    prompts = []

    def fake_post(_endpoint, _model, messages, _policy, schema):
        prompts.append((messages, schema))
        return _response(same, distinct)

    monkeypatch.setattr(runner, "post_completion", fake_post)
    row = runner._call(CASE, SPAN, OWNER, object())
    assert len(prompts) == 1
    assert (row["same_or_part_answer"], row["distinct_item_answer"]) == (same, distinct)
    assert (row["entity_link"], row["source_relation"], row["route"]) == (
        link,
        relation,
        route,
    )
    serialized = json.dumps(row, ensure_ascii=False)
    assert MESSAGE not in serialized
    prompt = json.dumps(prompts[0][0], ensure_ascii=False)
    assert MESSAGE in prompt
    assert "expected_relation" not in prompt and "event_status" not in prompt
    assert set(prompts[0][1]["properties"]) == {"same_or_part", "distinct_item"}


def test_invalid_response_does_not_create_relation(monkeypatch):
    monkeypatch.setattr(
        runner,
        "post_completion",
        lambda *_args: SimpleNamespace(content="{", finish_reason="stop"),
    )
    row = runner._call(CASE, SPAN, OWNER, object())
    assert row["same_or_part_answer"] is row["distinct_item_answer"] is None
    assert row["entity_link"] is row["source_relation"] is row["route"] is None
    assert (row["error_stage"], row["error_code"]) == ("contract", "invalid_json")
