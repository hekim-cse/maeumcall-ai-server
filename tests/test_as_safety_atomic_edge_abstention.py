"""Offline checks for the paired ES abstention wording probe."""

import argparse
import json

import pytest

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v1.event_owner import event_owner_schema
from experiments.as_safety_atomic_edges_v2 import run as probe
from experiments.as_safety_atomic_edges_v2 import verify
from experiments.as_safety_v2.transport import Completion, TransportError


def _inputs():
    return {key: path.read_bytes() for key, path in probe.INPUTS.items()}


def _cases():
    return {case["case_id"]: case for case in v1.load_request_cases(_inputs())}


def test_conditions_change_only_the_abstention_sentence():
    case = _cases()["ES01"]
    event = case["events"][0]
    baseline = probe.messages(case, event, "baseline")
    variant = probe.messages(case, event, "variant")
    assert baseline[0] == variant[0]
    assert (
        baseline[1]["content"].replace(probe.OLD_SENTENCE, probe.NEW_SENTENCE)
        == variant[1]["content"]
    )
    assert baseline[1]["content"].count(probe.OLD_SENTENCE) == 1
    assert probe.NEW_SENTENCE.count("unresolved") == 1
    schema = event_owner_schema(case["user_message"])
    assert set(schema["properties"]) == {
        "subject_span",
        "event_subject_kind",
        "event_subject_evidence_span",
    }


def test_frozen_request_hashes_cover_every_ordered_call_without_gold():
    hashes = probe._request_hashes(_inputs())
    assert set(hashes) == {f"{case_id}:{condition}" for case_id, condition in probe.ORDER}
    assert len(set(hashes.values())) == len(probe.ORDER)
    case = _cases()["ES01"]
    body = json.loads(
        probe.request_bytes(
            probe.messages(case, case["events"][0], "baseline"),
            event_owner_schema(case["user_message"]),
            probe._policy({"request_policy": v1.REQUEST_POLICY}),
        )
    )
    serialized = json.dumps(body, ensure_ascii=False)
    assert "hazard_owner_span" not in serialized
    assert "owner_to_target" not in serialized
    assert "expected_route" not in serialized
    assert "event_subject_kind" in serialized  # Output schema, not gold label.


def test_runner_records_ten_calls_and_does_not_retry_transport_error(tmp_path, monkeypatch):
    verified = _inputs()
    protocol = {
        **probe._identity(),
        "request_sha256_by_call": probe._request_hashes(verified),
    }
    monkeypatch.setattr(
        probe,
        "load_protocol",
        lambda protocol_path, model_path: (protocol, "protocol-sha", verified),
    )
    monkeypatch.setattr(probe.v4, "verify_container", lambda name, model_path: None)
    calls = []

    def fake_completion(messages, schema, *, policy, endpoint, model_id):
        calls.append(messages)
        if len(calls) == 1:
            raise TransportError("timeout")
        return Completion(
            json.dumps(
                {
                    "subject_span": None,
                    "event_subject_kind": "unresolved",
                    "event_subject_evidence_span": None,
                }
            ),
            "stop",
        )

    output = tmp_path / "journal.jsonl"
    private = tmp_path / "private"
    probe.run(
        argparse.Namespace(
            output=output,
            private_dir=private,
            protocol=tmp_path / "protocol.json",
            model_path=tmp_path / "model.gguf",
            container_name=probe.CONTAINER_NAME,
        ),
        completion_call=fake_completion,
    )
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert len(calls) == 10
    assert len(rows) == 11
    assert [(row["case_id"], row["condition"]) for row in rows[1:]] == list(probe.ORDER)
    assert rows[1]["error_code"] == "timeout"
    assert rows[1]["raw_sha256"] is None
    assert rows[2]["raw_sha256"] is not None
    assert not (private / "ES01-baseline.json.txt").exists()
    assert (private / "ES01-variant.json.txt").stat().st_mode & 0o777 == 0o600
    assert private.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize("tamper", ["wrong_hash", "duplicate_condition", "bad_status"])
def test_replay_rejects_tampered_request_or_response_metadata(tmp_path, tamper):
    sources = verify._source_cases(_inputs())
    protocol = {
        **probe._identity(),
        "request_sha256_by_call": probe._request_hashes(_inputs()),
    }
    rows = [{"event": "header", "protocol_sha256": "protocol-sha"}]
    for case_id, condition in probe.ORDER:
        rows.append(
            {
                "event": "result",
                "case_id": case_id,
                "event_index": 1,
                "condition": condition,
                "request_sha256": protocol["request_sha256_by_call"][f"{case_id}:{condition}"],
                "finish_reason": None,
                "error_code": "timeout",
                "http_status": None,
                "raw_sha256": None,
                "raw_bytes": None,
                "request_latency_ms": 1.0,
            }
        )
    if tamper == "wrong_hash":
        rows[1]["request_sha256"] = "0" * 64
    elif tamper == "duplicate_condition":
        rows[2]["condition"] = "baseline"
    else:
        rows[1]["http_status"] = 200
    journal = tmp_path / "journal.jsonl"
    journal.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    with pytest.raises(verify.VerificationError):
        verify._journal(journal, "protocol-sha", sources, protocol)


def test_full_replay_reports_fixed_denominators_and_reproduced_baseline(tmp_path, monkeypatch):
    verified = _inputs()
    protocol = {
        **probe._identity(),
        "request_sha256_by_call": probe._request_hashes(verified),
    }
    monkeypatch.setattr(
        verify,
        "check_protocol",
        lambda protocol_path, model_path: (protocol, "protocol-sha", verified),
    )
    prior_raw = json.dumps(
        {
            "subject_span": None,
            "event_subject_kind": "unresolved",
            "event_subject_evidence_span": None,
        }
    )
    prior_sha = probe.digest(prior_raw.encode())
    monkeypatch.setattr(
        verify.v1,
        "verify_result",
        lambda *args: {
            "event_calls": 19,
            "contract_pass": {"matched": 19},
            "protocol_sha256": verify.REFERENCE_PROTOCOL_SHA256,
        },
    )
    monkeypatch.setattr(
        verify.v1,
        "_read_journal",
        lambda *args: [
            {"case_id": case_id, "event_index": 1, "called": True, "raw_sha256": prior_sha}
            for case_id in probe.CASE_IDS
        ],
    )
    monkeypatch.setattr(verify.v1, "_private_raw", lambda *args: prior_raw)
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    rows = [{"event": "header", "protocol_sha256": "protocol-sha"}]
    for case_id, condition in probe.ORDER:
        raw_path = private / f"{case_id}-{condition}.json.txt"
        raw_path.write_text(prior_raw)
        raw_path.chmod(0o600)
        rows.append(
            {
                "event": "result",
                "case_id": case_id,
                "event_index": 1,
                "condition": condition,
                "request_sha256": protocol["request_sha256_by_call"][f"{case_id}:{condition}"],
                "finish_reason": "stop",
                "error_code": None,
                "http_status": None,
                "raw_sha256": prior_sha,
                "raw_bytes": len(prior_raw.encode()),
                "request_latency_ms": 1.0,
            }
        )
    journal = tmp_path / "journal.jsonl"
    journal.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    reference_protocol = v1.DATA / "as-safety-atomic-edge-v1-development-protocol.json"
    reference_journal = v1.DATA / "as-safety-atomic-edge-v1-development-journal.v1.jsonl"
    report = verify.verify_result(
        tmp_path / "protocol.json",
        tmp_path / "model.gguf",
        journal,
        private,
        reference_protocol,
        reference_journal,
        tmp_path / "reference-private",
    )
    assert report["historical_baseline_all_reproduced"] is True
    assert len(report["historical_baseline_reproduced"]) == 5
    assert len(report["paired_cases"]) == 10
    for condition in ("baseline", "variant"):
        result = report["summary"][condition]
        assert result["contract_pass"] == 5
        assert result["abstentions"] == 5
        assert result["B_exact_resolved"] == 0
        assert result["B_resolved_denominator"] == 4
        assert result["evidence_exact"] == 1
        assert result["resolved_evidence_exact"] == 0
        assert result["resolved_evidence_denominator"] == 4
        assert result["ES17_correct_abstention"] == 1
        assert result["ES17_false_resolution"] == 0
