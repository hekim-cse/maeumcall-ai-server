"""Exercise the next-version preflight and HTTP failure boundary without a model."""

import hashlib
import http.client
import json

import pytest

from scripts import as_safety_preflight_v3
from scripts.as_safety_pair_executor_v3 import Completion, run_pair_journal
from scripts.as_safety_preflight_v3 import run_frozen_pair, verify_frozen_sources
from scripts.verify_as_safety_pair_journal_v3 import verify_journal


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


def test_verifier_digest_mismatch_stops_before_model_request(tmp_path, monkeypatch):
    executor = as_safety_preflight_v3.EXECUTOR_SOURCE
    verifier = as_safety_preflight_v3.VERIFIER_SOURCE
    protocol = tmp_path / "protocol.json"
    protocol.write_text(
        json.dumps(
            {
                "executor_sha256": hashlib.sha256(executor.read_bytes()).hexdigest(),
                "verifier_sha256": hashlib.sha256(verifier.read_bytes()).hexdigest(),
            }
        )
    )
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
        validate=lambda arm, content, message: {},
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
            validate=lambda arm, content, message: {},
            route=lambda arm, decision: "confirming_safety_status",
        )
    assert not model_calls
    assert not journal.exists()


def test_missing_verifier_digest_is_rejected(tmp_path):
    protocol = tmp_path / "protocol.json"
    protocol.write_text(
        json.dumps(
            {
                "executor_sha256": hashlib.sha256(
                    as_safety_preflight_v3.EXECUTOR_SOURCE.read_bytes()
                ).hexdigest()
            }
        )
    )
    with pytest.raises(ValueError, match="missing or invalid verifier_sha256"):
        verify_frozen_sources(protocol)


def test_mandatory_source_path_cannot_be_substituted(tmp_path):
    protocol = tmp_path / "protocol.json"
    protocol.write_text("{}")
    with pytest.raises(ValueError, match="cannot be overridden"):
        verify_frozen_sources(protocol, {"verifier_sha256": tmp_path / "other.py"})


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
        validate=lambda arm, content, message: {},
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
