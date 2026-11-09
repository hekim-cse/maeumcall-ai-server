"""Exercise the next-version preflight and HTTP failure boundary without a model."""

import hashlib
import http.client
import json
import os
import stat

import pytest

from scripts import as_safety_pair_executor_v3, as_safety_preflight_v3
from scripts.as_safety_pair_executor_v3 import Completion, run_pair_journal
from scripts.as_safety_preflight_v3 import run_frozen_pair, verify_frozen_sources
from scripts.verify_as_safety_pair_journal_v3 import verify_journal


def bounded_schema(_arm, _message):
    return {
        "type": "object",
        "properties": {"bounded": {"enum": [True]}},
        "required": ["bounded"],
        "additionalProperties": False,
    }


@pytest.mark.parametrize(
    ("failure", "name"),
    [
        (http.client.BadStatusLine("private status line"), "BadStatusLine"),
        (http.client.LineTooLong("private header"), "LineTooLong"),
    ],
)
def test_http_protocol_error_is_recorded_and_second_arm_continues(tmp_path, failure, name):
    calls = []

    def request(arm, message):
        calls.append((arm, message))
        if len(calls) == 1:
            raise failure
        return Completion("{}", "stop")

    journal = tmp_path / "journal.jsonl"
    run_pair_journal(
        cases=[("N01", "private first"), ("N02", "private second")],
        journal=journal,
        protocol_sha256="a" * 64,
        request=request,
        validate=lambda arm, content, message: {"bounded": True},
        decision_schema=bounded_schema,
        route=lambda arm, decision: "confirming_safety_status",
    )
    assert calls == [
        ("baseline", "private first"),
        ("candidate", "private first"),
        ("candidate", "private second"),
        ("baseline", "private second"),
    ]
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    assert events[2]["error_stage"] == "response"
    assert events[2]["error_type"] == name
    assert events[2]["decision"] is None
    assert events[2]["route"] is None
    assert "private" not in journal.read_text()
    assert verify_journal(journal, ["N01", "N02"], "a" * 64)["arm_calls"] == 4


def test_journal_directory_is_synced_before_first_model_call(tmp_path, monkeypatch):
    synced_directory = False
    real_fsync = os.fsync

    def record_fsync(descriptor):
        nonlocal synced_directory
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            synced_directory = True
        real_fsync(descriptor)

    def request(arm, message):
        assert synced_directory
        return Completion("{}", "stop")

    monkeypatch.setattr(as_safety_pair_executor_v3.os, "fsync", record_fsync)
    run_pair_journal(
        cases=[("N01", "private")],
        journal=tmp_path / "journal.jsonl",
        protocol_sha256="a" * 64,
        request=request,
        validate=lambda arm, content, message: {"bounded": True},
        decision_schema=bounded_schema,
        route=lambda arm, decision: "confirming_safety_status",
    )


def test_unbounded_decision_is_not_persisted(tmp_path):
    journal = tmp_path / "journal.jsonl"
    run_pair_journal(
        cases=[("N01", "private")],
        journal=journal,
        protocol_sha256="a" * 64,
        request=lambda arm, message: Completion("private raw output", "stop"),
        validate=lambda arm, content, message: {"explanation": content},
        decision_schema=bounded_schema,
        route=lambda arm, decision: "confirming_safety_status",
    )
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    ends = [event for event in events if event["event"] == "end"]
    assert all(event["error_stage"] == "contract" and event["decision"] is None for event in ends)
    assert "private raw output" not in journal.read_text()


@pytest.mark.parametrize("mutate", [True, False])
def test_route_cannot_persist_mutated_decision_or_arbitrary_route(tmp_path, mutate):
    journal = tmp_path / "journal.jsonl"

    def route(_arm, decision):
        if mutate:
            decision["explanation"] = "private raw output"
            return "confirming_safety_status"
        return "private raw output"

    run_pair_journal(
        cases=[("N01", "private")],
        journal=journal,
        protocol_sha256="a" * 64,
        request=lambda arm, message: Completion("{}", "stop"),
        validate=lambda arm, content, message: {"bounded": True},
        decision_schema=bounded_schema,
        route=route,
    )
    ends = [
        event
        for event in (json.loads(line) for line in journal.read_text().splitlines())
        if event["event"] == "end"
    ]
    assert all(event["error_stage"] == "route" for event in ends)
    assert all(event["decision"] is None and event["route"] is None for event in ends)
    assert "private raw output" not in journal.read_text()


def test_interrupted_journal_cannot_replay(tmp_path):
    journal = tmp_path / "journal.jsonl"
    calls = []

    def interrupted(arm, message):
        calls.append(arm)
        raise KeyboardInterrupt

    def run():
        run_pair_journal(
            cases=[("N01", "private")],
            journal=journal,
            protocol_sha256="a" * 64,
            request=interrupted,
            validate=lambda arm, content, message: {"bounded": True},
            decision_schema=bounded_schema,
            route=lambda arm, decision: "confirming_safety_status",
        )

    with pytest.raises(KeyboardInterrupt):
        run()
    original = journal.read_bytes()
    with pytest.raises(FileExistsError, match="manual audit"):
        run()
    assert journal.read_bytes() == original
    assert calls == ["baseline"]


def test_verifier_digest_mismatch_stops_before_model_request(tmp_path, monkeypatch):
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps(frozen_source_hashes()))
    verify_frozen_sources(protocol)
    model_calls = []

    def request(arm, message):
        model_calls.append((arm, message))
        return Completion("{}", "stop")

    run_frozen_pair(
        protocol_path=protocol,
        cases=[("N00", "first private")],
        journal=tmp_path / "good.jsonl",
        request=request,
        validate=lambda arm, content, message: {"bounded": True},
        decision_schema=bounded_schema,
        route=lambda arm, decision: "confirming_safety_status",
    )
    assert len(model_calls) == 2
    model_calls.clear()
    changed_verifier = tmp_path / "changed_verifier.py"
    changed_verifier.write_text("changed after freeze")
    monkeypatch.setattr(as_safety_preflight_v3, "VERIFIER_SOURCE", changed_verifier)
    journal = tmp_path / "journal.jsonl"
    with pytest.raises(ValueError, match="frozen verifier_sha256 differs"):
        run_frozen_pair(
            protocol_path=protocol,
            cases=[("N01", "private")],
            journal=journal,
            request=request,
            validate=lambda arm, content, message: {"bounded": True},
            decision_schema=bounded_schema,
            route=lambda arm, decision: "confirming_safety_status",
        )
    assert not model_calls
    assert not journal.exists()


def test_missing_verifier_digest_is_rejected(tmp_path):
    protocol = tmp_path / "protocol.json"
    hashes = frozen_source_hashes()
    del hashes["verifier_sha256"]
    protocol.write_text(json.dumps(hashes))
    with pytest.raises(ValueError, match="missing or invalid verifier_sha256"):
        verify_frozen_sources(protocol)


def test_mandatory_source_path_cannot_be_substituted(tmp_path):
    protocol = tmp_path / "protocol.json"
    protocol.write_text("{}")
    with pytest.raises(ValueError, match="cannot be overridden"):
        verify_frozen_sources(protocol, {"verifier_sha256": tmp_path / "other.py"})


def test_imported_executor_must_match_frozen_source(tmp_path, monkeypatch):
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps(frozen_source_hashes()))
    monkeypatch.setattr(as_safety_preflight_v3, "IMPORTED_EXECUTOR_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="imported executor differs"):
        verify_frozen_sources(protocol)


def test_protocol_digest_uses_verified_snapshot(tmp_path, monkeypatch):
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps(frozen_source_hashes()))
    original_digest = hashlib.sha256(protocol.read_bytes()).hexdigest()
    original_runner = as_safety_preflight_v3.run_pair_journal

    def change_protocol_after_preflight(**kwargs):
        protocol.write_text('{"replaced": true}')
        original_runner(**kwargs)

    monkeypatch.setattr(as_safety_preflight_v3, "run_pair_journal", change_protocol_after_preflight)
    journal = tmp_path / "journal.jsonl"
    run_frozen_pair(
        protocol_path=protocol,
        cases=[("N01", "private")],
        journal=journal,
        request=lambda arm, message: Completion("{}", "stop"),
        validate=lambda arm, content, message: {"bounded": True},
        decision_schema=bounded_schema,
        route=lambda arm, decision: "confirming_safety_status",
    )
    header = json.loads(journal.read_text().splitlines()[0])
    assert header["protocol_sha256"] == original_digest


def frozen_source_hashes():
    paths = {
        "executor_sha256": as_safety_preflight_v3.EXECUTOR_SOURCE,
        "verifier_sha256": as_safety_preflight_v3.VERIFIER_SOURCE,
        "preflight_sha256": as_safety_preflight_v3.Path(as_safety_preflight_v3.__file__),
        "journal_shape_sha256": as_safety_preflight_v3.SHAPE_VERIFIER_SOURCE,
        "error_audit_sha256": as_safety_preflight_v3.ERROR_AUDIT_SOURCE,
    }
    return {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in paths.items()}


def test_verifier_dependency_digest_is_required(tmp_path):
    protocol = tmp_path / "protocol.json"
    hashes = frozen_source_hashes()
    del hashes["error_audit_sha256"]
    protocol.write_text(json.dumps(hashes))
    with pytest.raises(ValueError, match="missing or invalid error_audit_sha256"):
        verify_frozen_sources(protocol)


@pytest.mark.parametrize(
    ("stage", "decision", "finish_reason"),
    [
        ("route", {"unexpected": True}, "stop"),
        ("contract", None, "length"),
        ("response", None, "stop"),
    ],
)
def test_v3_verifier_rejects_impossible_error_metadata(tmp_path, stage, decision, finish_reason):
    journal = tmp_path / "journal.jsonl"
    run_pair_journal(
        cases=[("N01", "private")],
        journal=journal,
        protocol_sha256="a" * 64,
        request=lambda arm, message: Completion("{}", "stop"),
        validate=lambda arm, content, message: {"bounded": True},
        decision_schema=bounded_schema,
        route=lambda arm, bounded: "confirming_safety_status",
    )
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    events[2].update(
        decision=decision,
        route=None,
        error_stage=stage,
        error_type="ValueError",
        finish_reason=finish_reason,
    )
    journal.write_text("\n".join(json.dumps(event) for event in events) + "\n")
    with pytest.raises(ValueError):
        verify_journal(journal, ["N01"], "a" * 64)


@pytest.mark.parametrize("tamper", ["unknown_stage", "extra_field", "blank_error_type"])
def test_v3_verifier_rejects_invalid_structure_and_blank_error(tmp_path, tamper):
    journal = tmp_path / "journal.jsonl"
    run_pair_journal(
        cases=[("N01", "private")],
        journal=journal,
        protocol_sha256="a" * 64,
        request=lambda arm, message: Completion("{}", "stop"),
        validate=lambda arm, content, message: {"bounded": True},
        decision_schema=bounded_schema,
        route=lambda arm, decision: "confirming_safety_status",
    )
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    if tamper == "unknown_stage":
        events[2].update(decision=None, route=None, error_stage="unknown", error_type="ValueError")
    elif tamper == "extra_field":
        events[2]["raw_response"] = "private"
    else:
        events[2].update(decision=None, route=None, error_stage="response", error_type="  ")
    journal.write_text("\n".join(json.dumps(event) for event in events) + "\n")
    with pytest.raises(ValueError):
        verify_journal(journal, ["N01"], "a" * 64)
