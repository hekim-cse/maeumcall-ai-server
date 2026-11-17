"""Roundtrip and tamper checks for the development-only dual-query experiment."""

from __future__ import annotations

import hashlib
import json
import os
import stat

import pytest

from experiments.as_safety_dual_query_v1 import run as runner
from experiments.as_safety_dual_query_v1 import verify as auditor
from experiments.as_safety_v2.transport import Completion, RequestPolicy


def _cases():
    return runner.load_cases(runner.INPUTS["dataset"])


def _correct_decision(gold: dict, arm: str) -> str:
    relation = gold["owner_to_target"]
    return "yes" if relation == arm or (relation == "other" and arm == "distinct") else "no"


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ('{"decision":"maybe"}', "decision_enum_invalid"),
        ('{"decision":"yes","extra":0}', "decision_fields_invalid"),
        ('{"decision":"yes","decision":"no"}', "duplicate_key"),
        ('{"decision":"yes","x":NaN}', "nonfinite_number"),
    ],
)
def test_independent_raw_parser_rejects_invalid_contract(raw, code):
    with pytest.raises(auditor.ContractError) as caught:
        auditor.replay_decision(raw)
    assert caught.value.code == code


def test_order_and_oracle_denominator():
    cases = _cases()
    selected = runner.eligible_events(cases)
    assert len(selected) == 18
    assert len({case["id"] for _, _, case, _ in selected}) == 17
    assert "ES17-1" not in [key for key, _, _, _ in selected]
    order = runner.arm_order(cases)
    assert [item["arms"][0] for item in order].count("current") == 9
    assert [item["arms"][0] for item in order].count("distinct") == 9
    assert order == auditor_expected_order(cases)


def test_protocol_freezes_all_sources_inputs_and_balanced_order(monkeypatch):
    cases = _cases()
    sources = set(runner.REQUIRED_SOURCES)
    monkeypatch.setattr(runner, "_source_paths", lambda _commit: sources)
    monkeypatch.setattr(
        runner.v4,
        "_committed",
        lambda _commit, relative: (runner.ROOT / relative).read_bytes(),
    )
    protocol = runner.build_protocol("a" * 40, cases)
    assert set(protocol) == runner.PROTOCOL_FIELDS
    assert set(protocol["source_manifest"]) == sources
    assert set(protocol["input_hashes"]) == set(runner.INPUTS)
    assert protocol["arm_order"] == runner.arm_order(cases)
    assert len(protocol["event_order"]) == 18
    assert len(protocol["case_order"]) == 17
    assert protocol["retry_policy"] == "no_retry_manual_audit_on_interruption"


def auditor_expected_order(cases: list[dict]) -> list[dict]:
    return [
        {"event_id": key, "arms": list(auditor.ARMS if i % 2 == 0 else reversed(auditor.ARMS))}
        for i, (key, _, _, _) in enumerate(auditor._eligible_events(cases))
    ]


def test_single_call_raw_is_private_and_contract_is_reported(tmp_path):
    event_id, _, case, gold = runner.eligible_events(_cases())[0]
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    raw = '{"decision":"yes","decision":"no"}'
    calls = []

    def completion(messages, schema, *, policy):
        calls.append(messages)
        return Completion(raw, "stop")

    stage = runner.call_event(
        event_id,
        case,
        gold,
        "current",
        RequestPolicy(),
        private,
        completion_call=completion,
    )
    assert len(calls) == 1
    assert stage["status"] == "contract_error"
    assert stage["error_code"] == "duplicate_key"
    assert stage["decision"] is None
    stored = private / f"{event_id}-current.json.txt"
    assert stored.read_text() == raw
    assert stat.S_IMODE(stored.stat().st_mode) == 0o600


def test_safety_precedence_and_conservative_join():
    cases = _cases()
    rows = []
    for key, _, _, gold in runner.eligible_events(cases):
        for arm in runner.ARMS:
            rows.append(
                {
                    "event_id": key,
                    "arm": arm,
                    "stage": {
                        "status": "validated",
                        "decision": _correct_decision(gold, arm),
                        "request_latency_ms": 1.0,
                    },
                }
            )
    perfect = runner.summarize(rows, cases)
    assert perfect["relation_correct"] == 18
    assert perfect["route_correct"] == 17
    assert perfect["gate_met"] is True
    row = next(item for item in rows if item["event_id"] == "ES06-1" and item["arm"] == "distinct")
    row["stage"].update(status="contract_error", decision=None)
    degraded = runner.summarize(rows, cases)
    assert degraded["relation_correct"] == 17
    assert degraded["es06_route"] == "safety_action_required"
    assert degraded["gate_met"] is False
    assert degraded["contract_errors"] == 1


@pytest.fixture
def complete_journal(tmp_path, monkeypatch):
    cases = auditor.load_cases(auditor.DATASET)
    selected = auditor._eligible_events(cases)
    assignments = auditor_expected_order(cases)
    protocol = {"event_order": [item["event_id"] for item in assignments], "arm_order": assignments}
    monkeypatch.setattr(auditor, "check_protocol", lambda *_args: (protocol, "a" * 64))
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    rows = [{"event": "header", "protocol_sha256": "a" * 64}]
    audited = {}
    lookup = {key: gold for key, _, _, gold in selected}
    for assignment in assignments:
        key = assignment["event_id"]
        for arm in assignment["arms"]:
            decision = _correct_decision(lookup[key], arm)
            raw = json.dumps({"decision": decision}).encode()
            name = f"{key}-{arm}.json.txt"
            path = private / name
            path.write_bytes(raw)
            os.chmod(path, 0o600)
            stage = {
                "called": True,
                "status": "validated",
                "skip_reason": None,
                "error_code": None,
                "error_field": None,
                "finish_reason": "stop",
                "latency_ms": 3.0,
                "request_latency_ms": 2.0,
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "raw_bytes": len(raw),
                "decision": decision,
            }
            rows.extend(
                (
                    {"event": "begin", "event_id": key, "arm": arm},
                    {"event": "end", "event_id": key, "arm": arm, "stage": stage},
                )
            )
            audited[(key, arm)] = {
                "status": "validated",
                "decision": decision,
                "request_latency_ms": 2.0,
            }
    rows.append(auditor.summarize(audited, cases))
    journal = tmp_path / "journal.jsonl"

    def write():
        journal.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows),
            encoding="utf-8",
        )

    write()
    return rows, write, journal, private


def test_independent_replay_and_runner_agree(complete_journal):
    rows, _, journal, private = complete_journal
    result = auditor.verify(auditor.DATASET, journal, private, model_path=journal)
    assert result["private_raw_count"] == 36
    assert result["summary"]["gate_met"] is True
    summary = result["summary"]
    assert summary["question_request_latency_ms"] == {
        "current": {"count": 18, "p50": 2.0, "p95": 2.0},
        "distinct": {"count": 18, "p50": 2.0, "p95": 2.0},
    }
    assert summary["event_request_latency_p50_ms"] == 4.0
    assert summary["event_request_latency_p95_ms"] == 4.0
    assert summary["event_request_latency_count"] == 18
    assert summary["case_request_latency_p50_ms"] == 4.0
    assert summary["case_request_latency_p95_ms"] == 8.0
    assert summary["case_request_latency_count"] == 17
    assert summary["decided_relation_count"] == 18
    assert summary["decided_relation_correct"] == 18
    assert summary["relation_decision_denominator"] == 18
    assert summary["relation_decision_rate"] == 1.0
    assert summary["decided_relation_accuracy_denominator"] == 18
    assert summary["decided_relation_accuracy"] == 1.0
    assert sum(summary["abstention_reasons"].values()) == 0
    assert rows[-1] == {
        "event": "summary",
        **runner.summarize([item for item in rows if item["event"] == "end"], _cases()),
    }


def test_conflicting_answers_replay_as_unknown_and_confirmation(complete_journal):
    rows, write, journal, private = complete_journal
    end = next(
        item
        for item in rows
        if item["event"] == "end" and item["event_id"] == "ES01-1" and item["arm"] == "distinct"
    )
    raw = b'{"decision":"yes"}'
    (private / "ES01-1-distinct.json.txt").write_bytes(raw)
    end["stage"].update(
        decision="yes",
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        raw_bytes=len(raw),
    )
    audited = {
        (item["event_id"], item["arm"]): {
            "status": item["stage"]["status"],
            "decision": item["stage"]["decision"],
            "request_latency_ms": item["stage"]["request_latency_ms"],
        }
        for item in rows
        if item["event"] == "end"
    }
    rows[-1] = auditor.summarize(audited, auditor.load_cases(auditor.DATASET))
    write()
    result = auditor.verify(auditor.DATASET, journal, private, model_path=journal)
    assert result["summary"]["output_distribution"]["unknown"] == 1
    assert result["summary"]["abstention_reasons"]["contradiction"] == 1
    assert result["summary"]["decided_relation_count"] == 17
    assert result["summary"]["decided_relation_correct"] == 17
    assert result["summary"]["decided_relation_accuracy_denominator"] == 17
    assert result["summary"]["relation_decision_rate"] == round(17 / 18, 6)
    assert result["summary"]["decided_relation_accuracy"] == 1.0
    assert result["summary"]["directional_relation_errors"]["observed_current_to_unknown"] == 1
    assert result["summary"]["route_predictions"]["ES01"] == "confirming_safety_status"
    assert result["summary"]["gate_met"] is False


def test_abstention_reasons_partition_unknown_pairs(complete_journal):
    rows, _, _, _ = complete_journal
    ends = {
        (item["event_id"], item["arm"]): item["stage"] for item in rows if item["event"] == "end"
    }
    ends[("ES01-1", "distinct")]["decision"] = "yes"
    ends[("ES02-1", "current")]["decision"] = "no"
    ends[("ES02-1", "distinct")]["decision"] = "no"
    ends[("ES03-1", "current")]["decision"] = "unknown"
    ends[("ES04-1", "current")].update(status="contract_error", decision=None)
    public = [item for item in rows if item["event"] == "end"]
    runner_summary = runner.summarize(public, _cases())
    audited = {
        key: {
            "status": stage["status"],
            "decision": stage["decision"],
            "request_latency_ms": stage["request_latency_ms"],
        }
        for key, stage in ends.items()
    }
    verifier_summary = auditor.summarize(audited, auditor.load_cases(auditor.DATASET))
    assert verifier_summary == {"event": "summary", **runner_summary}
    assert runner_summary["abstention_reasons"] == {
        "error_pair": 1,
        "any_unknown": 1,
        "contradiction": 1,
        "both_no": 1,
    }
    assert runner_summary["unresolved_pairs"] == 4
    assert runner_summary["decided_relation_count"] == 14
    assert sum(runner_summary["abstention_reasons"].values()) == 4


@pytest.mark.parametrize("tamper", ["raw", "order", "summary", "decision", "extra"])
def test_tampering_is_rejected(complete_journal, tamper):
    rows, write, journal, private = complete_journal
    if tamper == "raw":
        (private / "ES01-1-current.json.txt").write_text('{"decision":"no"}')
    elif tamper == "order":
        rows[1], rows[3] = rows[3], rows[1]
    elif tamper == "summary":
        rows[-1]["route_correct"] = 0
    elif tamper == "decision":
        rows[2]["stage"]["decision"] = "unknown"
    else:
        rows[2]["stage"]["extra"] = True
    write()
    with pytest.raises(ValueError):
        auditor.verify(auditor.DATASET, journal, private, model_path=journal)
