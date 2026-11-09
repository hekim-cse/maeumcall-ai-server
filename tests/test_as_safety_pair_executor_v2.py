"""Failure injection for durable, no-retry paired model exposure."""

import http.client
import json

import pytest

from scripts.as_safety_pair_executor_v2 import Completion, run_pair_journal
from scripts.verify_as_safety_pair_journal_v2 import verify_journal


def read_events(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def run_with(path, request, cases=None, validate=None, route=None):
    run_pair_journal(
        cases=cases or [("X01", "private first"), ("X02", "private second")],
        journal=path,
        protocol_sha256="a" * 64,
        request=request,
        validate=validate or (lambda arm, content: {"decision": content}),
        route=route or (lambda arm, decision: "confirming_safety_status"),
    )


def test_truncated_response_records_error_and_continues_without_retry(tmp_path):
    calls = []

    def request(arm, message):
        calls.append((arm, message))
        if len(calls) == 1:
            raise http.client.IncompleteRead(b"partial", 9)
        return Completion("bounded", "stop")

    path = tmp_path / "journal.jsonl"
    run_with(path, request)
    assert calls == [
        ("baseline", "private first"),
        ("candidate", "private first"),
        ("candidate", "private second"),
        ("baseline", "private second"),
    ]
    events = read_events(path)
    assert [event["event"] for event in events] == [
        "header",
        "begin",
        "end",
        "begin",
        "end",
        "begin",
        "end",
        "begin",
        "end",
    ]
    assert events[2]["error_stage"] == "response"
    assert events[2]["error_type"] == "IncompleteRead"
    assert events[2]["route"] is None
    assert events[4]["route"] == "confirming_safety_status"
    assert "private first" not in path.read_text()
    assert "partial" not in path.read_text()
    assert verify_journal(path, ["X01", "X02"], "a" * 64) == {
        "cases": 2,
        "arm_calls": 4,
        "errors_by_stage": {"response": 1, "contract": 0, "route": 0},
    }
    with pytest.raises(FileExistsError, match="manual audit"):
        run_with(path, request)
    assert len(calls) == 4


def test_contract_and_route_errors_are_distinct(tmp_path):
    def validate(arm, content):
        if arm == "baseline":
            raise ValueError("raw model content must not be logged")
        return {"bounded": True}

    def route(arm, decision):
        raise KeyError("private route detail")

    path = tmp_path / "journal.jsonl"
    run_with(
        path,
        lambda arm, message: Completion("secret", "stop"),
        cases=[("X01", "text")],
        validate=validate,
        route=route,
    )
    ends = [event for event in read_events(path) if event["event"] == "end"]
    assert [(event["error_stage"], event["error_type"]) for event in ends] == [
        ("contract", "ValueError"),
        ("route", "KeyError"),
    ]
    assert all(event["decision"] is None and event["route"] is None for event in ends)
    assert "secret" not in path.read_text()
    assert "private route detail" not in path.read_text()


def test_length_termination_is_response_error(tmp_path):
    path = tmp_path / "journal.jsonl"
    run_with(path, lambda arm, message: Completion("{}", "length"), cases=[("X01", "text")])
    ends = [event for event in read_events(path) if event["event"] == "end"]
    assert all(event["error_stage"] == "response" for event in ends)
    assert all(event["finish_reason"] == "length" for event in ends)


def test_unknown_failure_preserves_begin_and_refuses_replay(tmp_path):
    calls = []

    def interrupted(arm, message):
        calls.append(arm)
        raise KeyboardInterrupt

    path = tmp_path / "journal.jsonl"
    with pytest.raises(KeyboardInterrupt):
        run_with(path, interrupted, cases=[("X01", "text")])
    assert [event["event"] for event in read_events(path)] == ["header", "begin"]
    with pytest.raises(FileExistsError, match="manual audit"):
        run_with(path, interrupted, cases=[("X01", "text")])
    assert calls == ["baseline"]
    with pytest.raises(ValueError, match="incomplete"):
        verify_journal(path, ["X01"], "a" * 64)


def test_verifier_rejects_swapped_arm_and_nonfinite_latency(tmp_path):
    path = tmp_path / "journal.jsonl"
    run_with(path, lambda arm, message: Completion("bounded", "stop"), cases=[("X01", "text")])
    events = read_events(path)
    events[3]["arm"] = "baseline"
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n")
    with pytest.raises(ValueError, match="call order"):
        verify_journal(path, ["X01"], "a" * 64)
    events[3]["arm"] = "candidate"
    events[2]["latency_ms"] = float("nan")
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n")
    with pytest.raises(ValueError, match="latency"):
        verify_journal(path, ["X01"], "a" * 64)
