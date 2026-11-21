"""Offline checks for the frozen E→B development control probe."""

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v4 import run as v4
from experiments.as_safety_atomic_edges_v5 import run as probe
from experiments.as_safety_atomic_edges_v5 import verify
from experiments.as_safety_v2.transport import Completion, TransportError

EXPECTED_ORDER = ("PC01", "NC01")
PROTOCOL_PATH = (
    probe.ROOT
    / "evals/structured_nlu/data/ai_heldout/as-safety-eb-controls-v5-development-protocol.json"
)
FROZEN_REQUEST_SHA = {
    "PC01": "332c359d8cd5420855baa32b2a0b70c739cb9b9f64fa2de91ea010ec91daaff8",
    "NC01": "9a3cfefe4721deb5f0cd1b9b08744f77305ac9d10c93ee28c75143e986c2e228",
}


def _cases():
    return probe._load_cases(probe.DATA.read_bytes())


def _protocol():
    cases = _cases()
    policy = probe._policy({"request_policy": v1.REQUEST_POLICY})
    return {
        **probe._identity(),
        "source_manifest": {"experiments/as_safety_atomic_edges_v5/verify.py": "frozen-test"},
        "request_sha256_by_call": {
            case_id: probe._request_sha(cases[case_id], policy) for case_id in EXPECTED_ORDER
        },
    }


def _response(case_id, *, mode="correct"):
    if case_id == "PC01":
        subject = _cases()["PC01"]["gold_subject_span"]
        kind = "location"
        if mode == "wrong":
            subject = None
            kind = "unresolved"
        elif mode == "wrong_b_and_kind":
            subject = {"clause_index": 1, "quote": "선풍기"}
            kind = "subject"
        elif mode == "wrong_kind":
            kind = "subject"
        elif mode == "malformed":
            subject = "선풍기 모터"
        elif mode == "bad_enum":
            kind = "not_a_kind"
        elif mode == "whitespace_quote":
            subject = {"clause_index": 2, "quote": " "}
    else:
        subject = None
        kind = "unresolved"
        if mode == "wrong":
            subject = {"clause_index": 1, "quote": "선풍기"}
            kind = "subject"
    payload = {"subject_span": subject, "event_subject_kind": kind}
    if mode == "extra_key":
        payload["unexpected"] = True
    return json.dumps(payload, ensure_ascii=False)


def test_reviewed_control_input_and_requests_match_v4_without_gold_labels():
    cases = _cases()
    assert tuple(cases) == EXPECTED_ORDER
    policy = probe._policy({"request_policy": v1.REQUEST_POLICY})
    protocol = _protocol()
    committed_protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    assert committed_protocol["request_sha256_by_call"] == FROZEN_REQUEST_SHA
    for case_id in EXPECTED_ORDER:
        case = cases[case_id]
        event = {"event_span": case["event_span"], "occurrence": case["occurrence"]}
        assert probe._outgoing(case) == v4.messages(case, event, "variant")
        assert probe._schema(case) == v4.subject_schema(case["user_message"])
        body = v4.request_bytes(probe._outgoing(case), probe._schema(case), policy, "variant")
        assert b"gold_subject_span" not in body and b"gold_kind" not in body
        assert b"expected_route" not in body and b"owner_to_target" not in body
        assert hashlib.sha256(body).hexdigest() == protocol["request_sha256_by_call"][case_id]
        assert verify._request_sha(case, protocol) == protocol["request_sha256_by_call"][case_id]
        assert (
            hashlib.sha256(body).hexdigest()
            == committed_protocol["request_sha256_by_call"][case_id]
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("review_status", "pending_user_review"),
        ("review_date", "2026-99-99"),
        ("provenance", "human_authored"),
    ],
)
def test_unapproved_or_misidentified_controls_are_rejected(field, value):
    payload = json.loads(probe.DATA.read_text())
    payload[field] = value
    raw = json.dumps(payload, ensure_ascii=False).encode()
    with pytest.raises(ValueError):
        probe._load_cases(raw)
    with pytest.raises(verify.VerificationError):
        verify._source_cases(raw)


def test_runner_keeps_fixed_order_after_timeout_and_never_retries(tmp_path, monkeypatch):
    protocol = _protocol()
    cases = _cases()
    monkeypatch.setattr(probe, "load_protocol", lambda *args: (protocol, "frozen-sha", cases))
    monkeypatch.setattr(probe.v4, "_verify_local_docker_endpoint", lambda: None)
    monkeypatch.setattr(probe.v4, "_container_identity", lambda name: ("same-id", "same-start"))
    monkeypatch.setattr(probe.server, "verify_container", lambda *args: None)
    calls = []

    def fake_completion(messages, schema, *, condition, policy, endpoint, model_id):
        request = v4.request_bytes(messages, schema, policy, condition)
        calls.append((messages, condition, hashlib.sha256(request).hexdigest()))
        if len(calls) == 1:
            raise TransportError("timeout")
        return Completion(_response("NC01"), "stop")

    output = tmp_path / "journal.jsonl"
    private = tmp_path / "private"
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
    assert tuple(row["case_id"] for row in rows[1:]) == EXPECTED_ORDER
    assert len(calls) == 2
    assert [call[2] for call in calls] == [
        protocol["request_sha256_by_call"][case_id] for case_id in EXPECTED_ORDER
    ]
    assert [call[1] for call in calls] == ["variant", "variant"]
    assert rows[1]["error_code"] == "timeout" and rows[1]["raw_sha256"] is None
    assert rows[2]["finish_reason"] == "stop"
    assert private.stat().st_mode & 0o777 == 0o700
    assert (private / "NC01.json.txt").stat().st_mode & 0o777 == 0o600


def test_runner_rejects_missing_journal_parent_before_private_creation(tmp_path, monkeypatch):
    private = tmp_path / "private"
    monkeypatch.setattr(probe, "JOURNAL", tmp_path / "missing" / "journal.jsonl")
    monkeypatch.setattr(probe, "PRIVATE_DIR", private)
    with pytest.raises(ValueError, match="journal parent"):
        probe.run(
            argparse.Namespace(
                output=tmp_path / "missing" / "journal.jsonl",
                private_dir=private,
                protocol=tmp_path / "protocol.json",
                model_path=tmp_path / "model.gguf",
                container_name=probe.CONTAINER_NAME,
            )
        )
    assert not private.exists()


def test_failed_journal_open_removes_only_new_empty_private_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "load_protocol", lambda *args: (_protocol(), "frozen-sha", _cases()))
    monkeypatch.setattr(probe.v4, "_verify_local_docker_endpoint", lambda: None)
    monkeypatch.setattr(probe.v4, "_container_identity", lambda name: ("same-id", "same-start"))
    monkeypatch.setattr(probe.server, "verify_container", lambda *args: None)
    output = tmp_path / "journal.jsonl"
    output.symlink_to(tmp_path / "missing-target")
    private = tmp_path / "private"
    monkeypatch.setattr(probe, "JOURNAL", output)
    monkeypatch.setattr(probe, "PRIVATE_DIR", private)
    with pytest.raises(FileExistsError):
        probe.run(
            argparse.Namespace(
                output=output,
                private_dir=private,
                protocol=tmp_path / "protocol.json",
                model_path=tmp_path / "model.gguf",
                container_name=probe.CONTAINER_NAME,
            )
        )
    assert not private.exists()
    assert output.is_symlink()


def test_runner_rejects_alternate_paths_before_loading_protocol(tmp_path, monkeypatch):
    canonical_output = tmp_path / "journal.jsonl"
    canonical_private = tmp_path / "private"
    monkeypatch.setattr(probe, "JOURNAL", canonical_output)
    monkeypatch.setattr(probe, "PRIVATE_DIR", canonical_private)
    alternate_output = tmp_path / "other.jsonl"
    with pytest.raises(ValueError, match="one-shot output paths"):
        probe.run(
            argparse.Namespace(
                output=alternate_output,
                private_dir=canonical_private,
                protocol=tmp_path / "protocol.json",
                model_path=tmp_path / "model.gguf",
                container_name=probe.CONTAINER_NAME,
            )
        )
    with pytest.raises(ValueError, match="one-shot output paths"):
        probe.run(
            argparse.Namespace(
                output=canonical_output,
                private_dir=tmp_path / "other-private",
                protocol=tmp_path / "protocol.json",
                model_path=tmp_path / "model.gguf",
                container_name=probe.CONTAINER_NAME,
            )
        )
    assert not alternate_output.exists()
    assert not canonical_private.exists()


def _replay(tmp_path, monkeypatch, *, positive="correct", negative="correct"):
    protocol = _protocol()
    cases = _cases()
    monkeypatch.setattr(verify, "check_protocol", lambda *args: (protocol, "frozen-sha", cases))
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    rows = [{"event": "header", "protocol_sha256": "frozen-sha"}]
    for case_id, mode in (("PC01", positive), ("NC01", negative)):
        if mode == "timeout":
            rows.append(
                {
                    "event": "result",
                    "case_id": case_id,
                    "request_sha256": protocol["request_sha256_by_call"][case_id],
                    "finish_reason": None,
                    "error_code": "timeout",
                    "http_status": None,
                    "raw_sha256": None,
                    "raw_bytes": None,
                    "request_latency_ms": 1.5,
                }
            )
            continue
        raw = _response(case_id, mode=mode)
        raw_bytes = raw.encode()
        path = private / f"{case_id}.json.txt"
        path.write_bytes(raw_bytes)
        path.chmod(0o600)
        rows.append(
            {
                "event": "result",
                "case_id": case_id,
                "request_sha256": protocol["request_sha256_by_call"][case_id],
                "finish_reason": "stop",
                "error_code": None,
                "http_status": None,
                "raw_sha256": hashlib.sha256(raw_bytes).hexdigest(),
                "raw_bytes": len(raw_bytes),
                "request_latency_ms": 1.5,
            }
        )
    journal = tmp_path / "journal.jsonl"
    journal.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    result = verify.verify_result(
        tmp_path / "protocol.json", tmp_path / "model.gguf", journal, private
    )
    return result, rows, journal, private


def test_replay_separates_positive_quote_kind_and_negative_abstention(tmp_path, monkeypatch):
    result, _, _, _ = _replay(tmp_path, monkeypatch)
    assert result["summary"]["contract_pass"] == 2
    assert result["summary"]["positive_valid_nonnull"] == 1
    assert result["summary"]["positive_quote_anchored"] == 1
    assert result["summary"]["positive_B_exact"] == 1
    assert result["summary"]["positive_kind_exact"] == 1
    assert result["summary"]["negative_correct_abstention"] == 1
    assert result["control_gate_pass"] is True
    assert result["official_accuracy_or_improvement_claim"] is False


@pytest.mark.parametrize(
    (
        "positive",
        "negative",
        "contract",
        "positive_nonnull",
        "positive_b",
        "positive_kind",
        "negative_abstain",
        "gate",
    ),
    [
        ("wrong", "correct", 2, 0, 0, 0, 1, False),
        ("wrong_kind", "correct", 2, 1, 1, 0, 1, True),
        ("wrong_b_and_kind", "correct", 2, 1, 0, 0, 1, True),
        ("malformed", "correct", 1, 0, 0, 0, 1, False),
        ("correct", "wrong", 2, 1, 1, 1, 0, False),
    ],
)
def test_replay_failure_types_do_not_become_control_success(
    tmp_path,
    monkeypatch,
    positive,
    negative,
    contract,
    positive_nonnull,
    positive_b,
    positive_kind,
    negative_abstain,
    gate,
):
    result, _, _, _ = _replay(tmp_path, monkeypatch, positive=positive, negative=negative)
    metrics = result["summary"]
    assert metrics["contract_pass"] == contract
    assert metrics["positive_valid_nonnull"] == positive_nonnull
    assert metrics["positive_quote_anchored"] == positive_nonnull
    assert metrics["positive_B_exact"] == positive_b
    assert metrics["positive_kind_exact"] == positive_kind
    assert metrics["negative_correct_abstention"] == negative_abstain
    assert result["control_gate_pass"] is gate


def test_replay_rejects_wrong_journal_order_or_request_hash(tmp_path, monkeypatch):
    result, rows, journal, _ = _replay(tmp_path, monkeypatch)
    assert result["control_gate_pass"]
    rows[1], rows[2] = rows[2], rows[1]
    journal.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    with pytest.raises(verify.VerificationError, match="journal request identity"):
        verify.verify_result(
            tmp_path / "protocol.json", tmp_path / "model.gguf", journal, tmp_path / "private"
        )
    rows[1], rows[2] = rows[2], rows[1]
    rows[1]["request_sha256"] = "0" * 64
    journal.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    with pytest.raises(verify.VerificationError, match="journal request identity"):
        verify.verify_result(
            tmp_path / "protocol.json", tmp_path / "model.gguf", journal, tmp_path / "private"
        )


def test_replay_rejects_private_raw_mutation(tmp_path, monkeypatch):
    _, _, journal, private = _replay(tmp_path, monkeypatch)
    (private / "PC01.json.txt").write_text("changed")
    with pytest.raises(verify.VerificationError, match="private response digest"):
        verify.verify_result(tmp_path / "protocol.json", tmp_path / "model.gguf", journal, private)


@pytest.mark.parametrize(
    ("mode", "expected_code"),
    [
        ("bad_enum", "subject_kind_invalid"),
        ("extra_key", "output_fields_invalid"),
        ("whitespace_quote", "quote_blank_or_invalid"),
    ],
)
def test_replay_rejects_invalid_enum_extra_field_and_blank_quote(
    tmp_path, monkeypatch, mode, expected_code
):
    result, _, _, _ = _replay(tmp_path, monkeypatch, positive=mode)
    assert result["summary"]["contract_pass"] == 1
    assert result["summary"]["contract_errors"] == 1
    assert result["summary"]["positive_evaluable"] is False
    assert result["per_case"][0]["contract_error_code"] == expected_code
    assert result["per_case"][0]["B_exact"] is None
    assert result["control_gate_pass"] is False


def test_negative_timeout_is_unevaluable_instead_of_wrong_abstention(tmp_path, monkeypatch):
    result, _, _, _ = _replay(tmp_path, monkeypatch, negative="timeout")
    assert result["summary"]["contract_pass"] == 1
    assert result["summary"]["transport_or_length_errors"] == 1
    assert result["summary"]["negative_evaluable"] is False
    assert result["per_case"][1]["valid_abstention"] is None
    assert result["per_case"][1]["false_resolution"] is None
    assert result["control_gate_pass"] is False


def test_journal_hash_refers_to_parsed_bytes_when_file_changes(tmp_path, monkeypatch):
    _, _, journal, private = _replay(tmp_path, monkeypatch)
    original = journal.read_bytes()
    parse = verify._journal

    def mutate_after_parse(raw, protocol_sha, cases, protocol):
        rows = parse(raw, protocol_sha, cases, protocol)
        journal.write_bytes(original + b"\n")
        return rows

    monkeypatch.setattr(verify, "_journal", mutate_after_parse)
    result = verify.verify_result(
        tmp_path / "protocol.json", tmp_path / "model.gguf", journal, private
    )
    assert result["journal_sha256"] == hashlib.sha256(original).hexdigest()


def test_protocol_scores_the_verified_case_snapshot_even_if_source_changes(tmp_path, monkeypatch):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"mock model")
    original_digest = verify._digest_file
    monkeypatch.setattr(
        verify,
        "_digest_file",
        lambda path: v1.MODEL_SHA if path == model else original_digest(path),
    )
    original_read = Path.read_bytes
    frozen_cases = probe.DATA.read_bytes()
    altered = json.loads(frozen_cases)
    altered["cases"][0]["gold_subject_span"]["quote"] = "모터"
    altered_cases = json.dumps(altered, ensure_ascii=False).encode("utf-8")
    data_reads = 0

    def read_with_later_mutation(path):
        nonlocal data_reads
        if path == verify.DATA:
            data_reads += 1
            return frozen_cases if data_reads == 1 else altered_cases
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", read_with_later_mutation)
    _, _, cases = verify.check_protocol(PROTOCOL_PATH, model)
    assert data_reads == 1
    assert cases["PC01"]["gold_subject_span"]["quote"] == "선풍기 모터"
