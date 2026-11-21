"""Offline contract and replay tests for the answer-given format oracle."""

import argparse
import hashlib
import json

import pytest

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v4 import run as v4
from experiments.as_safety_atomic_edges_v6 import run as probe
from experiments.as_safety_atomic_edges_v6 import verify
from experiments.as_safety_v2.transport import Completion, TransportError

EXPECTED_ORDER = ("F1", "F2")
FROZEN_REQUEST_SHA = {
    "F1": "2f2410f963fc463aea8973cd909e98d8945545b45d4fed4aa7613f340d383dc8",
    "F2": "61a1f6e227d07c96dbb521c3876b1c6a082a2ce2b0869fada3cf498a229e1716",
}


def _case():
    return probe._case(probe.v5.DATA.read_bytes())


def _protocol():
    case = _case()
    policy = probe.v5._policy({"request_policy": v1.REQUEST_POLICY})
    return {
        **probe._identity(),
        "source_manifest": {"experiments/as_safety_atomic_edges_v6/verify.py": "test"},
        "request_sha256_by_call": {
            arm: probe.request_sha(case, arm, policy) for arm in EXPECTED_ORDER
        },
    }


def _response(mode="correct"):
    subject = {"clause_index": 2, "quote": "선풍기 모터"}
    kind = "location"
    if mode == "null":
        subject, kind = None, "unresolved"
    elif mode == "wrong_b":
        subject = {"clause_index": 1, "quote": "선풍기"}
    elif mode == "wrong_kind":
        kind = "subject"
    elif mode == "bad_enum":
        kind = "bad_kind"
    elif mode == "whitespace":
        subject = {"clause_index": 2, "quote": " "}
    elif mode == "string":
        subject = "선풍기 모터"
    payload = {"subject_span": subject, "event_subject_kind": kind}
    if mode == "extra_key":
        payload["unexpected"] = True
    return json.dumps(payload, ensure_ascii=False)


def test_oracle_requests_are_distinct_and_independently_rebuilt():
    case = _case()
    policy = probe.v5._policy({"request_policy": v1.REQUEST_POLICY})
    protocol = _protocol()
    assert tuple(protocol["call_order"]) == EXPECTED_ORDER
    assert protocol["request_sha256_by_call"] == FROZEN_REQUEST_SHA
    original = v4.messages(
        case,
        {"event_span": case["event_span"], "occurrence": case["occurrence"]},
        "variant",
    )
    assert probe.messages(case, "F1")[0] == original[0]
    assert probe.messages(case, "F2")[0] == original[0]
    assert probe.messages(case, "F1")[1]["content"].startswith(original[1]["content"])
    assert probe.messages(case, "F2")[1]["content"].startswith(original[1]["content"])
    assert (
        '{"subject_span":{"clause_index":2,"quote":"선풍기 모터"}'
        in probe.messages(case, "F1")[1]["content"]
    )
    assert '{"subject_span"' not in probe.messages(case, "F2")[1]["content"]
    assert "2번 문장의 선풍기 모터" in probe.messages(case, "F2")[1]["content"]
    for arm in EXPECTED_ORDER:
        body = v4.request_bytes(
            probe.messages(case, arm), probe.v5._schema(case), policy, "variant"
        )
        assert hashlib.sha256(body).hexdigest() == FROZEN_REQUEST_SHA[arm]
        assert verify._request_sha(case, arm, protocol) == FROZEN_REQUEST_SHA[arm]
    assert probe._identity()["oracle_labels_in_both_requests"] is True


def test_unreviewed_cases_cannot_enter_oracle():
    payload = json.loads(probe.v5.DATA.read_text())
    payload["review_status"] = "pending_user_review"
    with pytest.raises(ValueError):
        probe._case(json.dumps(payload, ensure_ascii=False).encode())
    with pytest.raises(verify.VerificationError):
        verify._case(json.dumps(payload, ensure_ascii=False).encode())


def test_runner_uses_fixed_order_without_retry_after_timeout(tmp_path, monkeypatch):
    protocol = _protocol()
    monkeypatch.setattr(probe, "load_protocol", lambda *args: (protocol, "frozen-sha", _case()))
    monkeypatch.setattr(probe.v4, "_verify_local_docker_endpoint", lambda: None)
    monkeypatch.setattr(probe.v4, "_container_identity", lambda name: ("same-id", "same-start"))
    monkeypatch.setattr(probe.server, "verify_container", lambda *args: None)
    calls = []

    def fake_completion(messages, schema, *, condition, policy, endpoint, model_id):
        body = v4.request_bytes(messages, schema, policy, condition)
        calls.append(hashlib.sha256(body).hexdigest())
        if len(calls) == 1:
            raise TransportError("timeout")
        return Completion(_response(), "stop")

    output, private = tmp_path / "journal.jsonl", tmp_path / "private"
    monkeypatch.setattr(probe, "JOURNAL", output)
    monkeypatch.setattr(probe, "PRIVATE_DIR", private)
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
    assert [row["arm"] for row in rows[1:]] == list(EXPECTED_ORDER)
    assert calls == [FROZEN_REQUEST_SHA[arm] for arm in EXPECTED_ORDER]
    assert rows[1]["error_code"] == "timeout" and rows[1]["raw_sha256"] is None
    assert rows[2]["finish_reason"] == "stop"
    assert private.stat().st_mode & 0o777 == 0o700
    assert (private / "F2.json.txt").stat().st_mode & 0o777 == 0o600


def test_runner_rejects_alternate_or_existing_paths_before_calls(tmp_path, monkeypatch):
    output, private = tmp_path / "journal.jsonl", tmp_path / "private"
    monkeypatch.setattr(probe, "JOURNAL", output)
    monkeypatch.setattr(probe, "PRIVATE_DIR", private)
    args = argparse.Namespace(
        output=tmp_path / "different.jsonl",
        private_dir=private,
        protocol=tmp_path / "protocol.json",
        model_path=tmp_path / "model.gguf",
        container_name=probe.CONTAINER_NAME,
    )
    with pytest.raises(ValueError, match="one-shot"):
        probe.run(args)
    args.output = output
    output.write_text("partial")
    with pytest.raises(FileExistsError, match="partial or existing"):
        probe.run(args)
    assert not private.exists()


def test_verifier_rejects_alternate_paths_before_replay(tmp_path, monkeypatch):
    monkeypatch.setattr(verify, "check_protocol", lambda *args: pytest.fail("unexpected replay"))
    with pytest.raises(verify.VerificationError, match="one-shot"):
        verify.verify_result(
            tmp_path / "protocol.json",
            tmp_path / "model.gguf",
            tmp_path / "alternate.jsonl",
            tmp_path / "private",
        )


def _replay(tmp_path, monkeypatch, first="correct", second="correct"):
    protocol = _protocol()
    case = _case()
    monkeypatch.setattr(verify, "check_protocol", lambda *args: (protocol, "frozen-sha", case))
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    rows = [{"event": "header", "protocol_sha256": "frozen-sha"}]
    for arm, mode in zip(EXPECTED_ORDER, (first, second), strict=True):
        row = {
            "event": "result",
            "arm": arm,
            "request_sha256": protocol["request_sha256_by_call"][arm],
            "finish_reason": None,
            "error_code": None,
            "http_status": None,
            "raw_sha256": None,
            "raw_bytes": None,
            "request_latency_ms": 2.5,
        }
        if mode == "timeout":
            row["error_code"] = "timeout"
        else:
            raw = _response(mode).encode()
            path = private / f"{arm}.json.txt"
            path.write_bytes(raw)
            path.chmod(0o600)
            row.update(
                finish_reason="stop",
                raw_sha256=hashlib.sha256(raw).hexdigest(),
                raw_bytes=len(raw),
            )
        rows.append(row)
    journal = tmp_path / "journal.jsonl"
    journal.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    monkeypatch.setattr(verify, "JOURNAL", journal)
    monkeypatch.setattr(verify, "PRIVATE_DIR", private)
    result = verify.verify_result(
        tmp_path / "protocol.json", tmp_path / "model.gguf", journal, private
    )
    return result, rows, journal, private


def test_replay_exact_object_is_structural_and_not_extraction_accuracy(tmp_path, monkeypatch):
    result, _, _, _ = _replay(tmp_path, monkeypatch)
    assert result["summary"]["contract_pass"] == 2
    assert result["summary"]["full_object_match"] == 2
    assert result["summary"]["given_B_exact"] == 2
    assert result["summary"]["given_kind_exact"] == 2
    assert result["summary"]["valid_nonnull"] == 2
    assert result["extraction_accuracy_evaluated"] is False
    assert result["gold_in_both_requests"] is True


@pytest.mark.parametrize("mode", ["null", "wrong_b", "wrong_kind"])
def test_replay_separates_null_and_partial_object_from_full_match(tmp_path, monkeypatch, mode):
    result, _, _, _ = _replay(tmp_path, monkeypatch, first=mode)
    assert result["summary"]["contract_pass"] == 2
    assert result["summary"]["full_object_match"] == 1
    assert result["per_arm"][0]["full_object_match"] is False
    assert result["per_arm"][0]["valid_null"] is (mode == "null")


@pytest.mark.parametrize("mode", ["bad_enum", "extra_key", "whitespace", "string"])
def test_replay_malformed_output_is_not_semantic_success(tmp_path, monkeypatch, mode):
    result, _, _, _ = _replay(tmp_path, monkeypatch, first=mode)
    assert result["summary"]["contract_pass"] == 1
    assert result["summary"]["contract_errors"] == 1
    assert result["summary"]["full_object_match"] == 1
    assert result["per_arm"][0]["full_object_match"] is None
    assert result["per_arm"][0]["contract_error_code"] is not None


def test_timeout_is_unevaluable_and_not_an_oracle_failure(tmp_path, monkeypatch):
    result, _, _, _ = _replay(tmp_path, monkeypatch, first="timeout")
    assert result["summary"]["transport_or_length_errors"] == 1
    assert result["per_arm"][0]["full_object_match"] is None
    assert result["per_arm"][0]["valid_null"] is None


def test_journal_order_and_request_hash_drift_are_rejected(tmp_path, monkeypatch):
    _, rows, _, _ = _replay(tmp_path, monkeypatch)
    rows[1]["arm"], rows[2]["arm"] = rows[2]["arm"], rows[1]["arm"]
    raw = ("\n".join(json.dumps(row) for row in rows) + "\n").encode()
    with pytest.raises(verify.VerificationError, match="request identity"):
        verify._journal(raw, "frozen-sha", _protocol(), _case())
    rows[1]["arm"], rows[2]["arm"] = rows[2]["arm"], rows[1]["arm"]
    rows[1]["request_sha256"] = "0" * 64
    raw = ("\n".join(json.dumps(row) for row in rows) + "\n").encode()
    with pytest.raises(verify.VerificationError, match="request identity"):
        verify._journal(raw, "frozen-sha", _protocol(), _case())


def test_verifier_reports_hash_of_same_journal_bytes_it_scored(tmp_path, monkeypatch):
    original = verify._journal

    def mutate_after_parse(raw, *args):
        rows = original(raw, *args)
        journal.write_bytes(b"different later bytes")
        return rows

    result, _, journal, _ = _replay(tmp_path, monkeypatch)
    original_sha = result["journal_sha256"]
    monkeypatch.setattr(verify, "_journal", mutate_after_parse)
    result2 = verify.verify_result(
        tmp_path / "protocol.json", tmp_path / "model.gguf", journal, tmp_path / "private"
    )
    assert result2["journal_sha256"] == original_sha
    assert hashlib.sha256(journal.read_bytes()).hexdigest() != original_sha


def test_reference_hashes_match_v5_record():
    assert probe.v5.digest(probe.REFERENCE_PROTOCOL.read_bytes()) == probe.REFERENCE_PROTOCOL_SHA
    assert probe.v5.digest(probe.REFERENCE_JOURNAL.read_bytes()) == probe.REFERENCE_JOURNAL_SHA
    assert verify._digest(probe.REFERENCE_PROTOCOL.read_bytes()) == verify.REFERENCE_PROTOCOL_SHA
    assert verify._digest(probe.REFERENCE_JOURNAL.read_bytes()) == verify.REFERENCE_JOURNAL_SHA
