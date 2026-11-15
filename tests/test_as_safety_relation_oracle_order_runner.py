"""Owner-oracle relation-order runner keeps labels, order and failures bounded."""

from __future__ import annotations

import json
import stat
from collections import Counter

import pytest

from experiments.as_safety_relation_oracle_order_v1 import run as runner
from experiments.as_safety_v2.transport import Completion, RequestPolicy, TransportError
from experiments.as_safety_v4.cases import load_cases


def _cases():
    return load_cases(runner.INPUTS["dataset"])


def test_eligible_event_order_and_first_arm_balance():
    selected = runner.eligible_events(_cases())
    ids = runner.event_order(_cases())
    assert len(ids) == 18
    assert ids[5:7] == ["ES06-1", "ES06-2"]
    assert "ES17-1" not in ids
    order = runner.arm_order(_cases())
    assert [row["event_id"] for row in order] == ids
    first = Counter(
        (gold["owner_to_target"], assignment["arms"][0])
        for assignment, (_, _, _, gold) in zip(order, selected, strict=True)
    )
    assert first == {
        ("current", "forward"): 5,
        ("current", "reverse"): 4,
        ("other", "forward"): 4,
        ("other", "reverse"): 5,
    }


def test_prompt_contains_oracle_b_without_scoring_labels_and_order_only_changes_definitions():
    _, _, case, gold = runner.eligible_events(_cases())[0]
    forward = runner.relation_messages(case, gold, "forward")
    reverse = runner.relation_messages(case, gold, "reverse")
    assert forward[1] == reverse[1]
    body = json.loads(forward[1]["content"])
    assert set(body) == {"user_message", "target", "event_span", "hazard_owner_span", "occurrence"}
    assert body["hazard_owner_span"] == gold["hazard_owner_span"]
    assert "owner_to_target" not in json.dumps(forward, ensure_ascii=False)
    assert "expected_route" not in json.dumps(forward, ensure_ascii=False)
    common = forward[0]["content"].split("\n")[0]
    assert reverse[0]["content"].split("\n")[0] == common
    assert forward[0]["content"].split("\n")[1:] == list(runner.DEFINITIONS.values())
    assert reverse[0]["content"].split("\n")[1:] == list(reversed(runner.DEFINITIONS.values()))
    assert runner.relation_schema()["properties"]["relation"]["enum"] == [
        "current",
        "other",
        "unknown",
    ]


@pytest.mark.parametrize(
    "raw,code",
    [
        ("not json", "invalid_json"),
        ('{"relation":"invalid"}', "relation_enum_invalid"),
        ('{"relation":"current","reason":"x"}', "relation_fields_invalid"),
        ('{"relation":"current","relation":"other"}', "duplicate_key"),
    ],
)
def test_contract_failure_keeps_raw_and_one_call(tmp_path, raw, code):
    event_id, _, case, gold = runner.eligible_events(_cases())[0]
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    calls = []

    def fake_completion(messages, schema, *, policy):
        calls.append((messages, schema, policy))
        return Completion(raw, "stop")

    stage = runner.call_event(
        event_id,
        case,
        gold,
        "forward",
        RequestPolicy(),
        private,
        completion_call=fake_completion,
    )
    assert len(calls) == 1
    assert stage["status"] == "contract_error"
    assert stage["error_code"] == code
    assert stage["relation"] is None
    stored = private / f"{event_id}-forward.json.txt"
    assert stored.read_text() == raw
    assert stat.S_IMODE(stored.stat().st_mode) == 0o600
    assert stage["raw_sha256"] == runner.v4.digest(raw.encode())


def test_transport_failure_is_single_call_and_safe_confirmation(tmp_path):
    selected = runner.eligible_events(_cases())
    event_id, _, case, gold = next(item for item in selected if item[0] == "ES09-1")
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise TransportError("connection_error")

    stage = runner.call_event(
        event_id,
        case,
        gold,
        "forward",
        RequestPolicy(),
        private,
        completion_call=fail,
    )
    assert len(calls) == 1
    assert stage["status"] == "response_error"
    assert stage["relation"] is None
    assert stage["raw_sha256"] is None
    assert list(private.iterdir()) == []
    rows = [{"event_id": event_id, "arm": "forward", "stage": stage}]
    assert runner._routes(rows, [case], "forward")["ES09"] == "confirming_safety_status"


def test_es06_safety_priority_and_paired_summary():
    cases = _cases()
    rows = []
    for event_id, _, _, gold in runner.eligible_events(cases):
        for arm in runner.ARMS:
            relation = gold["owner_to_target"]
            rows.append(
                {
                    "event_id": event_id,
                    "arm": arm,
                    "stage": {
                        "status": "validated",
                        "relation": relation,
                        "request_latency_ms": 1.0,
                    },
                }
            )
    # Even if ES06's other-source event is invalid, the observed current event
    # still forces safety action in that case.
    for row in rows:
        if row["event_id"] == "ES06-1" and row["arm"] == "reverse":
            row["stage"]["status"] = "contract_error"
            row["stage"]["relation"] = None
    summary = runner.summarize(rows, cases)
    assert summary["arms"]["forward"]["relation_correct"] == 18
    assert summary["arms"]["reverse"]["relation_correct"] == 17
    assert summary["arms"]["reverse"]["es06_route"] == "safety_action_required"
    assert summary["arms"]["reverse"]["route_correct"] == 17
    assert summary["arms"]["reverse"]["contract_errors"] == 1
    assert summary["arms"]["reverse"]["response_errors"] == 0
    assert summary["paired"]["forward_correct_reverse_wrong"] == 1
    assert summary["paired"]["arm_prediction_agreement"] == 17
    assert summary["gate_met"] is False


def test_all_correct_oracle_gates_only_this_development_diagnostic():
    cases = _cases()
    rows = [
        {
            "event_id": event_id,
            "arm": arm,
            "stage": {
                "status": "validated",
                "relation": gold["owner_to_target"],
                "request_latency_ms": 1.0,
            },
        }
        for event_id, _, _, gold in runner.eligible_events(cases)
        for arm in runner.ARMS
    ]
    summary = runner.summarize(rows, cases)
    assert summary["gate_met"] is True
    assert summary["claim_scope"] == runner.SCOPE
    assert summary["arms"]["forward"]["category_correct"] == {
        "observed_current": 8,
        "uncertain_current": 1,
        "observed_other": 9,
    }


def test_protocol_contains_frozen_order_and_refuses_uncommitted_or_dirty(tmp_path, monkeypatch):
    commit = "a" * 40
    cases = _cases()
    sources = set(runner.REQUIRED_SOURCES)
    monkeypatch.setattr(runner, "_source_paths", lambda _: sources)
    monkeypatch.setattr(
        runner.v4, "_committed", lambda _commit, relative: (runner.ROOT / relative).read_bytes()
    )
    protocol = runner.build_protocol(commit, cases)
    assert set(protocol) == runner.PROTOCOL_FIELDS
    assert len(protocol["event_order"]) == 18
    assert len(protocol["case_order"]) == 17
    assert protocol["arm_order"] == runner.arm_order(cases)
    assert protocol["route_policy"]["multi_event_example"].startswith("ES06:")
    assert set(protocol["source_manifest"]) == sources
    assert set(protocol["input_hashes"]) == set(runner.INPUTS)
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    path = tmp_path / "protocol.json"
    raw = (json.dumps(protocol) + "\n").encode()
    path.write_bytes(raw)
    model = tmp_path / "model.gguf"
    model.write_bytes(b"test")
    monkeypatch.setattr(runner, "build_protocol", lambda *_: protocol)
    monkeypatch.setattr(runner, "load_cases", lambda _: cases)
    monkeypatch.setattr(runner.v4, "digest_file", lambda _: runner.MODEL_SHA)
    monkeypatch.setattr(runner.v4, "_git", lambda *args: b"wrong" if args[0] == "show" else b"")
    with pytest.raises(ValueError, match="committed"):
        runner.load_protocol(path, model)
    monkeypatch.setattr(runner.v4, "_git", lambda *args: raw if args[0] == "show" else b" M run.py")
    with pytest.raises(ValueError, match="checkout"):
        runner.load_protocol(path, model)
