"""Offline checks for the frozen ES subject-only development probe."""

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v3 import run as reference
from experiments.as_safety_atomic_edges_v4 import run as probe
from experiments.as_safety_atomic_edges_v4 import verify
from experiments.as_safety_v2.transport import Completion, TransportError

EXPECTED_ORDER = (
    ("ES01", "baseline"),
    ("ES01", "variant"),
    ("ES03", "variant"),
    ("ES03", "baseline"),
    ("ES09", "baseline"),
    ("ES09", "variant"),
    ("ES17", "variant"),
    ("ES17", "baseline"),
    ("ES18", "baseline"),
    ("ES18", "variant"),
)


def _inputs():
    return {key: path.read_bytes() for key, path in probe.INPUTS.items()}


def _cases():
    return {case["case_id"]: case for case in v1.load_request_cases(_inputs())}


def test_baseline_request_is_identical_to_v3_and_variant_has_no_gold_or_evidence():
    cases = _cases()
    policy = probe._policy({"request_policy": v1.REQUEST_POLICY})
    hashes = probe._request_hashes(_inputs())
    assert len(hashes) == 10
    for case_id in probe.CASE_IDS:
        case = cases[case_id]
        event = case["events"][0]
        baseline_messages = probe.messages(case, event, "baseline")
        assert baseline_messages == reference.messages(case, event, "baseline")
        baseline_schema = probe.event_owner_schema(case["user_message"])
        baseline_bytes = probe.request_bytes(baseline_messages, baseline_schema, policy, "baseline")
        assert baseline_bytes == reference.request_bytes(
            baseline_messages, baseline_schema, policy, "baseline"
        )
        assert hashes[f"{case_id}:baseline"] == probe._historical_hashes()[f"{case_id}:baseline"]
        variant_schema = probe.subject_schema(case["user_message"])
        variant_bytes = probe.request_bytes(
            probe.messages(case, event, "variant"), variant_schema, policy, "variant"
        )
        body = json.loads(variant_bytes)
        assert body["response_format"] == {"type": "json_object", "schema": variant_schema}
        assert set(variant_schema["properties"]) == {"subject_span", "event_subject_kind"}
        assert set(variant_schema["required"]) == {"subject_span", "event_subject_kind"}
        assert "event_subject_evidence_span" not in variant_bytes.decode()
        assert "hazard_owner_span" not in variant_bytes.decode()
        assert "owner_to_target" not in variant_bytes.decode()
        assert "expected_route" not in variant_bytes.decode()
        assert hashes[f"{case_id}:variant"] == probe.digest(variant_bytes)


def test_independent_request_rebuild_matches_runner_without_importing_candidate():
    inputs = _inputs()
    sources = verify._source_cases(inputs)
    hashes = probe._request_hashes(inputs)
    identity = probe._identity()
    assert all(
        verify._request_sha(sources[case_id], condition, identity)
        == hashes[f"{case_id}:{condition}"]
        for case_id, condition in probe.ORDER
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"subject_span":null,"event_subject_kind":"unresolved"}', None),
        ('{"subject_span":"기기","event_subject_kind":"subject"}', "quote fields invalid"),
        ('{"subject_span":null,"event_subject_kind":"subject"}', "unresolved spans inconsistent"),
        ('{"subject_span":null,"event_subject_kind":"unknown"}', "event subject kind invalid"),
        (
            '{"subject_span":{"clause_index":1,"quote":" "},"event_subject_kind":"subject"}',
            "quote blank or invalid",
        ),
        (
            '{"subject_span":null,"event_subject_kind":"unresolved","extra":1}',
            "output fields differ",
        ),
        (
            '{"subject_span":null,"subject_span":null,"event_subject_kind":"unresolved"}',
            "duplicate JSON key",
        ),
    ],
)
def test_subject_only_replay_enforces_exact_contract(raw, expected):
    source = verify._source_cases(_inputs())["ES17"]
    if expected is None:
        assert verify.replay_subject_only(
            raw, source["user_message"], source["events"][0]["event_span"]
        ) == {"subject_span": None, "event_subject_kind": "unresolved"}
    else:
        with pytest.raises(verify.v1.VerificationError, match=expected):
            verify.replay_subject_only(
                raw, source["user_message"], source["events"][0]["event_span"]
            )


def test_subject_only_replay_accepts_anchored_quote_and_rejects_unanchored():
    source = verify._source_cases(_inputs())["ES03"]
    message = source["user_message"]
    clauses = verify.v1._clauses(message)
    quote = source["events"][0]["hazard_owner_span"]
    raw = json.dumps({"subject_span": quote, "event_subject_kind": "subject"}, ensure_ascii=False)
    assert (
        verify.replay_subject_only(raw, message, source["events"][0]["event_span"])["subject_span"][
            "quote"
        ]
        == quote["quote"]
    )
    bad = json.dumps(
        {
            "subject_span": {"clause_index": len(clauses), "quote": "없는 구절"},
            "event_subject_kind": "subject",
        },
        ensure_ascii=False,
    )
    with pytest.raises(verify.v1.VerificationError, match="not uniquely anchored"):
        verify.replay_subject_only(bad, message, source["events"][0]["event_span"])


def test_runner_keeps_order_after_first_timeout_and_never_retries(tmp_path, monkeypatch):
    verified = _inputs()
    protocol = {**probe._identity(), "request_sha256_by_call": probe._request_hashes(verified)}
    monkeypatch.setattr(
        probe, "load_protocol", lambda protocol_path, model_path: (protocol, "frozen-sha", verified)
    )
    monkeypatch.setattr(probe.v4, "verify_container", lambda name, model_path: None)
    monkeypatch.setattr(probe, "_container_identity", lambda name: ("same-id", "same-start"))
    monkeypatch.setattr(probe, "_verify_local_docker_endpoint", lambda: None)
    calls = []

    def fake_completion(messages, schema, *, condition, policy, endpoint, model_id):
        outbound_sha = hashlib.sha256(
            probe.request_bytes(messages, schema, policy, condition)
        ).hexdigest()
        calls.append((condition, tuple(schema["required"]), messages, outbound_sha))
        if len(calls) == 1:
            raise TransportError("timeout")
        content = (
            {
                "subject_span": None,
                "event_subject_kind": "unresolved",
                "event_subject_evidence_span": None,
            }
            if condition == "baseline"
            else {"subject_span": None, "event_subject_kind": "unresolved"}
        )
        return Completion(json.dumps(content), "stop")

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
    assert probe.ORDER == EXPECTED_ORDER
    assert [(r["case_id"], r["condition"]) for r in rows[1:]] == list(EXPECTED_ORDER)
    assert [r["condition"] for r in rows[1:]] == [call[0] for call in calls]
    assert [call[3] for call in calls] == [
        protocol["request_sha256_by_call"][f"{case_id}:{condition}"]
        for case_id, condition in EXPECTED_ORDER
    ]
    assert calls[0][0] == "baseline" and calls[1][0] == "variant"
    assert set(calls[0][1]) == {
        "subject_span",
        "event_subject_kind",
        "event_subject_evidence_span",
    }
    assert set(calls[1][1]) == {"subject_span", "event_subject_kind"}
    assert rows[1]["error_code"] == "timeout"
    assert rows[1]["raw_sha256"] is None
    assert private.stat().st_mode & 0o777 == 0o700
    assert (private / "ES01-variant.json.txt").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("host", ["tcp://127.0.0.1:2375", "ssh://example.invalid"])
def test_runner_rejects_nonlocal_docker_host_before_container_inspection(monkeypatch, host):
    monkeypatch.setenv("DOCKER_HOST", host)
    with pytest.raises(ValueError, match="local Unix socket"):
        probe._verify_local_docker_endpoint()


def test_runner_rejects_remote_docker_context(monkeypatch):
    monkeypatch.delenv("DOCKER_HOST", raising=False)

    def fake_run(command, **kwargs):
        class Result:
            stdout = "desktop-linux\n" if command[-1] == "show" else "tcp://remote:2375\n"

        return Result()

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    with pytest.raises(ValueError, match="context must use a local Unix socket"):
        probe._verify_local_docker_endpoint()


def test_runner_rejects_missing_journal_parent_before_private_dir(tmp_path):
    private = tmp_path / "private"
    with pytest.raises(ValueError, match="journal parent directory"):
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


def test_failed_journal_creation_removes_new_empty_private_dir(tmp_path, monkeypatch):
    verified = _inputs()
    protocol = {**probe._identity(), "request_sha256_by_call": probe._request_hashes(verified)}
    monkeypatch.setattr(
        probe, "load_protocol", lambda protocol_path, model_path: (protocol, "frozen-sha", verified)
    )
    monkeypatch.setattr(probe, "_verify_local_docker_endpoint", lambda: None)
    monkeypatch.setattr(probe.v4, "verify_container", lambda name, model_path: None)
    monkeypatch.setattr(probe, "_container_identity", lambda name: ("same-id", "same-start"))
    output = tmp_path / "journal.jsonl"
    output.symlink_to(tmp_path / "missing-target")
    private = tmp_path / "private"
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


def test_verifier_rejects_changed_on_disk_source(monkeypatch):
    original = verify._digest_file

    def changed(path: Path):
        if path == Path(verify.__file__):
            return "0" * 64
        return original(path)

    monkeypatch.setattr(verify, "_digest_file", changed)
    with pytest.raises(verify.VerificationError, match="verifier source changed"):
        verify._check_loaded_verifier()


def test_prepare_rejects_outside_protocol_path_before_creating_file(tmp_path):
    path = tmp_path / "protocol.json"
    with pytest.raises(ValueError, match="inside repository"):
        probe.prepare_protocol(path, tmp_path / "model.gguf")
    assert not path.exists()


def test_load_protocol_rejects_float_timeout_before_model_check(tmp_path):
    protocol = {
        **probe._identity(),
        "frozen_code_commit": "0" * 40,
        "source_manifest": {},
        "input_hashes": {},
        "request_sha256_by_call": {},
    }
    protocol["request_policy"] = {**protocol["request_policy"], "timeout_seconds": 180.0}
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="timeout type"):
        probe.load_protocol(path, tmp_path / "model.gguf")
    with pytest.raises(verify.VerificationError, match="timeout type"):
        verify.check_protocol(path, tmp_path / "model.gguf")


def _synthetic_replay(tmp_path, monkeypatch, *, es01_variant=None, es17_variant=None):
    inputs = _inputs()
    protocol = {**probe._identity(), "request_sha256_by_call": probe._request_hashes(inputs)}
    monkeypatch.setattr(
        verify,
        "check_protocol",
        lambda protocol_path, model_path: (protocol, "protocol-sha", inputs),
    )
    baseline = json.dumps(
        {
            "subject_span": None,
            "event_subject_kind": "unresolved",
            "event_subject_evidence_span": None,
        }
    )
    variant_default = json.dumps({"subject_span": None, "event_subject_kind": "unresolved"})
    reference_rows = [
        {
            "case_id": case_id,
            "condition": condition,
            "raw_sha256": probe.digest(baseline.encode()),
            "raw_bytes": len(baseline.encode()),
        }
        for case_id, condition in probe.ORDER
    ]
    monkeypatch.setattr(verify.v3, "check_protocol", lambda *args: ({}, "reference-sha", inputs))
    monkeypatch.setattr(verify.v3, "_source_cases", lambda *args: verify._source_cases(inputs))
    monkeypatch.setattr(verify.v3, "_journal", lambda *args: reference_rows)
    monkeypatch.setattr(verify.v3, "_raw", lambda *args: baseline)
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    reference_private = tmp_path / "reference-private"
    reference_private.mkdir(mode=0o700)
    for row in reference_rows:
        path = reference_private / f"{row['case_id']}-{row['condition']}.json.txt"
        path.write_text(baseline)
        path.chmod(0o600)
    journal_rows = [{"event": "header", "protocol_sha256": "protocol-sha"}]
    for case_id, condition in probe.ORDER:
        raw = (
            baseline
            if condition == "baseline"
            else (
                es01_variant
                if case_id == "ES01" and es01_variant is not None
                else es17_variant
                if case_id == "ES17" and es17_variant is not None
                else variant_default
            )
        )
        path = private / f"{case_id}-{condition}.json.txt"
        path.write_text(raw)
        path.chmod(0o600)
        journal_rows.append(
            {
                "event": "result",
                "case_id": case_id,
                "event_index": 1,
                "condition": condition,
                "request_sha256": protocol["request_sha256_by_call"][f"{case_id}:{condition}"],
                "finish_reason": "stop",
                "error_code": None,
                "http_status": None,
                "raw_sha256": probe.digest(raw.encode()),
                "raw_bytes": len(raw.encode()),
                "request_latency_ms": 1.25,
            }
        )
    journal = tmp_path / "journal.jsonl"
    journal.write_text("\n".join(json.dumps(row) for row in journal_rows) + "\n")
    return verify.verify_result(
        tmp_path / "protocol.json",
        tmp_path / "model.gguf",
        journal,
        private,
        probe.REFERENCE_PROTOCOL,
        probe.REFERENCE_JOURNAL,
        reference_private,
    )


def test_full_replay_keeps_baseline_evidence_and_variant_subject_denominators(
    tmp_path, monkeypatch
):
    result = _synthetic_replay(tmp_path, monkeypatch)
    assert result["historical_baseline_all_reproduced"] is True
    assert len(result["paired_cases"]) == 10
    baseline = result["summary"]["baseline"]
    variant = result["summary"]["variant"]
    assert baseline["contract_pass"] == variant["contract_pass"] == 5
    assert baseline["B_resolved_denominator"] == variant["B_resolved_denominator"] == 4
    assert baseline["B_valid_resolved_cases"] == variant["B_valid_resolved_cases"] == 4
    assert baseline["kind_valid_cases"] == variant["kind_valid_cases"] == 5
    assert baseline["evidence_exact"] == 1
    assert "evidence_exact" not in variant
    assert baseline["ES17_correct_abstention"] == variant["ES17_correct_abstention"] == 1
    assert variant["ES17_evaluable"] is True
    assert variant["request_latency_ms_sum"] == 6.25
    assert result["token_usage"] == "not_collected_by_completion_transport"


def test_full_replay_distinguishes_invalid_es17_from_safe_abstention(tmp_path, monkeypatch):
    invalid = json.dumps({"subject_span": "문자열", "event_subject_kind": "location"})
    result = _synthetic_replay(tmp_path, monkeypatch, es17_variant=invalid)
    variant = result["summary"]["variant"]
    assert variant["contract_pass"] == 4
    assert variant["contract_errors"] == 1
    assert variant["ES17_evaluable"] is False
    assert variant["ES17_correct_abstention"] == 0
    assert variant["ES17_false_resolution"] == 0
    assert (
        next(
            row
            for row in result["paired_cases"]
            if row["case_id"] == "ES17" and row["condition"] == "variant"
        )["contract_error_code"]
        == "quote_fields_invalid"
    )


def test_full_replay_counts_valid_b_but_does_not_score_missing_evidence(tmp_path, monkeypatch):
    source = verify._source_cases(_inputs())["ES01"]
    expected_b = source["events"][0]["hazard_owner_span"]
    raw = json.dumps(
        {"subject_span": expected_b, "event_subject_kind": "subject"}, ensure_ascii=False
    )
    result = _synthetic_replay(tmp_path, monkeypatch, es01_variant=raw)
    variant = result["summary"]["variant"]
    assert variant["B_exact_resolved"] == 1
    assert variant["contract_pass"] == 5
    assert variant["ES17_correct_abstention"] == 1
    assert "evidence_exact" not in variant


def test_full_replay_excludes_invalid_resolved_case_from_accuracy(tmp_path, monkeypatch):
    invalid = json.dumps({"subject_span": "임의 문자열", "event_subject_kind": "location"})
    result = _synthetic_replay(tmp_path, monkeypatch, es01_variant=invalid)
    variant = result["summary"]["variant"]
    assert variant["contract_pass"] == 4
    assert variant["B_valid_resolved_cases"] == 3
    assert variant["B_resolved_denominator"] == 4
    assert variant["B_exact_resolved"] == 0
    assert variant["kind_valid_cases"] == 4
    assert variant["ES17_evaluable"] is True
