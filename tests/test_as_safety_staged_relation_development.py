"""Check staged call gating and independent journal reconstruction."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from scripts import run_as_safety_staged_relation_development as runner
from scripts.probe_as_safety_staged_relation import (
    EVENT_STATUSES,
    SOURCE_RELATIONS,
    combine_stages,
    route_staged,
)
from scripts.verify_as_safety_staged_relation_development import _end, _route_candidate


def _response(decision: dict):
    return SimpleNamespace(content=json.dumps(decision), finish_reason="stop")


def test_observed_event_calls_source_stage_and_records_bounded_decision(monkeypatch):
    replies = iter(
        [
            _response({"event_index": 2, "event_status": "observed"}),
            _response({"product_index": 1, "source_index": 2, "source_relation": "current_part"}),
        ]
    )
    messages = []

    def fake_post(_endpoint, _model, turns, _policy, _schema):
        messages.append(turns[1]["content"])
        return next(replies)

    monkeypatch.setattr(runner, "post_completion", fake_post)
    row = runner._run_arm(
        "candidate", "제 노트북을 접수합니다. 배터리에서 연기가 납니다.", object()
    )
    assert row["route"] == "safety_action_required"
    assert row["call_count"] == 2
    assert row["error_stage"] is None
    assert messages[1].endswith("event_index=2")
    assert "연기가 납니다" not in json.dumps(row, ensure_ascii=False)
    _end(
        {**row, "case_id": "RE01", "arm": "candidate"},
        "candidate",
        "제 노트북을 접수합니다. 배터리에서 연기가 납니다.",
    )


def test_nonoccurring_event_skips_source_but_remains_scored(monkeypatch):
    calls = []

    def fake_post(*args):
        calls.append(args)
        return _response({"event_index": 1, "event_status": "nonoccurring"})

    monkeypatch.setattr(runner, "post_completion", fake_post)
    row = runner._run_arm("candidate", "불이 날까 봐 걱정됩니다.", object())
    assert len(calls) == 1
    assert row["route"] == "collecting_service_request"
    assert row["call_count"] == 1
    assert row["stage2"]["skip_reason"] == "no_active_event"
    _end({**row, "case_id": "V01", "arm": "candidate"}, "candidate", "불이 날까 봐 걱정됩니다.")


def test_second_call_failure_is_a_case_error(monkeypatch):
    calls = 0

    def fake_post(*_args):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response({"event_index": 1, "event_status": "observed"})
        raise TimeoutError("secret raw prompt must not be recorded")

    monkeypatch.setattr(runner, "post_completion", fake_post)
    row = runner._run_arm("candidate", "제 배터리에서 불꽃이 났습니다.", object())
    assert row["call_count"] == 2
    assert row["route"] is None
    assert row["error_stage"] == "stage2_response"
    assert row["error_type"] == "TimeoutError"
    assert "secret" not in json.dumps(row)
    _end(
        {**row, "case_id": "RE01", "arm": "candidate"},
        "candidate",
        "제 배터리에서 불꽃이 났습니다.",
    )


@pytest.mark.parametrize(
    ("reply", "expected_stage", "expected_type", "expected_finish"),
    [
        (TimeoutError("private request text"), "stage1_response", "TimeoutError", None),
        (
            SimpleNamespace(content="{", finish_reason="stop"),
            "stage1_contract",
            "JSONDecodeError",
            "stop",
        ),
        (
            SimpleNamespace(
                content='{"event_index":1,"event_status":"observed"}', finish_reason="length"
            ),
            "stage1_response",
            "ValueError",
            "length",
        ),
    ],
)
def test_first_stage_failure_skips_source_and_verifies(
    monkeypatch, reply, expected_stage, expected_type, expected_finish
):
    calls = []

    def fake_post(*args):
        calls.append(args)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(runner, "post_completion", fake_post)
    message = "제 노트북에서 불꽃이 났습니다."
    row = runner._run_arm("candidate", message, object())
    assert len(calls) == 1
    assert row["call_count"] == 1
    assert row["decision"] is None and row["route"] is None
    assert row["stage2"]["skip_reason"] == "upstream_failure"
    assert row["stage1"]["finish_reason"] == expected_finish
    assert row["error_stage"] == expected_stage
    assert row["error_type"] == expected_type
    assert "private request text" not in json.dumps(row)
    _end({**row, "case_id": "RE01", "arm": "candidate"}, "candidate", message)


def test_second_stage_contract_failure_is_recorded_and_verifies(monkeypatch):
    replies = iter(
        [
            _response({"event_index": 1, "event_status": "observed"}),
            _response(
                {"product_index": 1, "source_index": None, "source_relation": "current_part"}
            ),
        ]
    )
    monkeypatch.setattr(runner, "post_completion", lambda *_args: next(replies))
    message = "제 노트북 배터리에서 연기가 납니다."
    row = runner._run_arm("candidate", message, object())
    assert row["call_count"] == 2
    assert row["decision"] is None and row["route"] is None
    assert row["stage2"]["error_stage"] == "contract"
    assert row["stage2"]["finish_reason"] == "stop"
    assert row["error_stage"] == "stage2_contract"
    assert row["error_type"] == "ValueError"
    _end({**row, "case_id": "RE01", "arm": "candidate"}, "candidate", message)


@pytest.mark.parametrize(
    ("reply", "expected_route", "expected_error"),
    [
        (
            _response({"evidence_index": 1, "target": "current", "assertion": "observed"}),
            "safety_action_required",
            None,
        ),
        (SimpleNamespace(content="{", finish_reason="stop"), None, "stage1_contract"),
    ],
)
def test_baseline_is_single_call_and_verifies(monkeypatch, reply, expected_route, expected_error):
    calls = []

    def fake_post(*args):
        calls.append(args)
        return reply

    monkeypatch.setattr(runner, "post_completion", fake_post)
    message = "제 노트북에서 연기가 납니다."
    row = runner._run_arm("baseline", message, object())
    assert len(calls) == 1
    assert row["call_count"] == 1
    assert row["stage2"]["skip_reason"] == "baseline_single_call"
    assert row["route"] == expected_route
    assert row["error_stage"] == expected_error
    _end({**row, "case_id": "RE01", "arm": "baseline"}, "baseline", message)


@pytest.mark.parametrize(
    ("status", "relation"),
    [
        ("none", "none"),
        ("nonoccurring", "none"),
        *(
            (status, relation)
            for status in EVENT_STATUSES
            if status in {"observed", "uncertain"}
            for relation in SOURCE_RELATIONS
        ),
    ],
)
def test_independent_route_matches_candidate_for_every_valid_state(status, relation):
    inactive = status in {"none", "nonoccurring"}
    event = {
        "event_index": None if status == "none" else 1,
        "event_status": status,
    }
    source = None
    if not inactive:
        source = {
            "product_index": 1,
            "source_index": None if relation == "unknown" else 1,
            "source_relation": relation,
        }
    decision = combine_stages(event, source)
    assert _route_candidate(decision) == route_staged(decision)


def test_independent_verifier_rejects_tampered_call_count_and_route(monkeypatch):
    monkeypatch.setattr(
        runner,
        "post_completion",
        lambda *_args: _response({"event_index": None, "event_status": "none"}),
    )
    row = {
        **runner._run_arm("candidate", "노트북 A/S를 신청합니다.", object()),
        "case_id": "V01",
        "arm": "candidate",
    }
    changed = copy.deepcopy(row)
    changed["call_count"] = 2
    with pytest.raises(ValueError, match="call count"):
        _end(changed, "candidate", "노트북 A/S를 신청합니다.")
    changed = copy.deepcopy(row)
    changed["route"] = "safety_action_required"
    with pytest.raises(ValueError, match="saved route"):
        _end(changed, "candidate", "노트북 A/S를 신청합니다.")
