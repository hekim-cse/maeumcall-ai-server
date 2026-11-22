"""Contract, no-gold, one-shot, and independent replay checks for v9."""

from __future__ import annotations

import argparse
import hashlib
import json

import pytest

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v4 import run as v4
from experiments.as_safety_atomic_edges_v9 import run as probe
from experiments.as_safety_atomic_edges_v9 import verify
from experiments.as_safety_v2.transport import Completion, TransportError


def _cases():
    return probe._cases(probe.v5.DATA.read_bytes())


def _protocol(*, token_count: int = 100):
    cases = _cases()
    policy = probe.v5._policy({"request_policy": v1.REQUEST_POLICY})
    return {
        **probe._identity(),
        "candidate_manifest": probe._candidate_manifest(cases),
        "input_tokens_by_call": {call: token_count for call in probe.ORDER},
        "source_manifest": {"experiments/as_safety_atomic_edges_v9/verify.py": "test"},
        "request_sha256_by_call": {
            call: probe.request_sha(cases[call[:4]], call[-1], policy) for call in probe.ORDER
        },
    }


def _response(case_id: str, mode: str = "correct") -> str:
    if case_id == "PC01":
        span = {"clause_index": 2, "quote": "선풍기 모터"}
        kind = "location"
        if mode == "wrong_b":
            span = {"clause_index": 1, "quote": "선풍기"}
        elif mode == "wrong_kind":
            kind = "subject"
        elif mode == "null":
            span, kind = None, "unresolved"
        elif mode == "illegal_kind":
            kind = "not_an_allowed_kind"
        elif mode == "whitespace_quote":
            span = {"clause_index": 2, "quote": " "}
    else:
        span, kind = None, "unresolved"
        if mode == "false_nonnull":
            span, kind = {"clause_index": 1, "quote": "선풍기"}, "subject"
    payload = {"subject_span": span, "event_subject_kind": kind}
    if mode == "extra_key":
        payload["unexpected"] = True
    return json.dumps(payload, ensure_ascii=False)


def test_full_request_matches_v7_and_nominal_rows_only_change_candidate_list():
    cases = _cases()
    policy = probe.v5._policy({"request_policy": v1.REQUEST_POLICY})
    reference = json.loads(probe.REFERENCE_V7_PROTOCOL.read_bytes())
    for case_id, case in cases.items():
        full = probe.messages(case, "F")
        nominal = probe.messages(case, "N")
        reverse = probe.messages(case, "R")
        assert full == probe.v7.messages(case, "B")
        assert nominal[0] == full[0] == reverse[0]
        full_rows = probe._candidate_rows(case, "F")
        nominal_rows = probe._candidate_rows(case, "N")
        assert full[1]["content"].endswith("\n".join(full_rows))
        assert nominal[1]["content"].endswith("\n".join(nominal_rows))
        assert reverse[1]["content"].endswith("\n".join(reversed(nominal_rows)))
        assert (
            nominal[1]["content"].split("\n".join(nominal_rows))[0]
            == full[1]["content"].split("\n".join(full_rows))[0]
        )
        assert set(nominal_rows).issubset(full_rows)
        for arm in "FNR":
            assert probe.request_sha(case, arm, policy) == verify._request_sha(
                case, arm, _protocol()
            )
        assert (
            probe.request_sha(case, "F", policy)
            == reference["request_sha256_by_call"][f"{case_id}-B"]
        )
        assert all(
            "gold_subject_span" not in json.dumps(probe.messages(case, arm), ensure_ascii=False)
            and "gold_kind" not in json.dumps(probe.messages(case, arm), ensure_ascii=False)
            for arm in "FNR"
        )
        assert case_id in {"PC01", "NC01"}
    assert probe._candidate_manifest(cases) == verify._candidate_manifest(cases)
    assert probe._candidate_manifest(cases)["PC01"]["candidate_count_by_arm"] == {
        "F": 22,
        "N": 7,
        "R": 7,
    }
    assert probe._candidate_manifest(cases)["NC01"]["candidate_count_by_arm"] == {
        "F": 35,
        "N": 4,
        "R": 4,
    }


def test_tokenizer_preflight_requires_exact_counts_below_context(monkeypatch):
    cases = _cases()
    policy = probe.v5._policy({"request_policy": v1.REQUEST_POLICY})
    seen = []

    reference = json.loads(probe.REFERENCE_V7_PROTOCOL.read_bytes())
    calls = iter(probe.ORDER)

    def count(body):
        seen.append(body)
        call = next(calls)
        return reference["input_tokens_by_call"][f"{call[:4]}-B"] if call.endswith("-F") else 100

    monkeypatch.setattr(probe, "_tokenize_request", count)
    assert probe._token_counts(cases, policy) == {
        call: reference["input_tokens_by_call"][f"{call[:4]}-B"] if call.endswith("-F") else 100
        for call in probe.ORDER
    }
    assert len(seen) == 6
    monkeypatch.setattr(probe, "_tokenize_request", lambda body: 100)
    with pytest.raises(ValueError, match="v7 full tokenizer count differs"):
        probe._token_counts(cases, policy)
    monkeypatch.setattr(probe, "_tokenize_request", lambda body: 4096 - policy.max_tokens)
    with pytest.raises(ValueError, match="context budget"):
        probe._token_counts(cases, policy)


def test_tokenizer_unavailable_fails_closed(monkeypatch):
    class OfflineOpener:
        def open(self, *args, **kwargs):
            raise OSError("offline")

    monkeypatch.setattr(probe, "build_opener", lambda *handlers: OfflineOpener())
    with pytest.raises(ValueError, match="tokenizer endpoint unavailable"):
        probe._tokenize_request(b"{}")


def test_tokenizer_rejects_oversized_response(monkeypatch):
    class OversizedResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, length):
            assert length == 4097
            return b"x" * length

    class OversizedOpener:
        def open(self, *args, **kwargs):
            return OversizedResponse()

    monkeypatch.setattr(probe, "build_opener", lambda *handlers: OversizedOpener())
    with pytest.raises(ValueError, match="tokenizer response too large"):
        probe._tokenize_request(b"{}")


def test_gold_value_perturbation_cannot_change_outgoing_requests():
    cases = _cases()
    changed = json.loads(json.dumps(cases, ensure_ascii=False))
    changed["PC01"]["gold_subject_span"] = {"clause_index": 1, "quote": "선풍기"}
    changed["PC01"]["gold_kind"] = "subject"
    policy = probe.v5._policy({"request_policy": v1.REQUEST_POLICY})
    for arm in "FNR":
        assert probe.messages(changed["PC01"], arm) == probe.messages(cases["PC01"], arm)
        assert probe.request_sha(changed["PC01"], arm, policy) == probe.request_sha(
            cases["PC01"], arm, policy
        )
    assert probe._candidate_manifest(changed) == probe._candidate_manifest(cases)


def test_protocol_timeout_requires_exact_integer_before_replay(tmp_path):
    protocol = _protocol()
    protocol["request_policy"] = dict(protocol["request_policy"])
    protocol["request_policy"]["timeout_seconds"] = 180.0
    protocol["frozen_code_commit"] = "0" * 40
    protocol["input_hashes"] = {}
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="request timeout type differs"):
        probe.load_protocol(path, tmp_path / "model.gguf")
    with pytest.raises(verify.VerificationError, match="request timeout type differs"):
        verify.check_protocol(path, tmp_path / "model.gguf")


def test_tokenizer_disables_proxy_and_rejects_redirect(monkeypatch):
    captured = {}

    class RedirectingOpener:
        def __init__(self, handlers):
            self.handlers = handlers

        def open(self, request, *, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            redirect = next(
                handler for handler in self.handlers if isinstance(handler, probe._NoRedirect)
            )
            return redirect.redirect_request(
                request, None, 302, "move", {}, "https://example.com/receive-private-prompt"
            )

    def make_opener(*handlers):
        captured["handlers"] = handlers
        return RedirectingOpener(handlers)

    monkeypatch.setattr(probe, "build_opener", make_opener)
    with pytest.raises(ValueError, match="tokenizer endpoint unavailable"):
        probe._tokenize_request(b'{"messages":[{"role":"user","content":"private"}]}')
    assert any(
        isinstance(handler, probe.ProxyHandler) and handler.proxies == {}
        for handler in captured["handlers"]
    )
    assert captured["request"].full_url == "http://127.0.0.1:18081/v1/chat/completions/input_tokens"
    assert captured["request"].get_method() == "POST"
    assert captured["timeout"] == 30


def test_runner_fixed_order_no_retry_and_private_raw(tmp_path, monkeypatch):
    protocol = _protocol()
    cases = _cases()
    monkeypatch.setattr(probe, "load_protocol", lambda *args: (protocol, "fixed-sha", cases))
    monkeypatch.setattr(probe, "_token_counts", lambda *args: protocol["input_tokens_by_call"])
    monkeypatch.setattr(probe.v4, "_verify_local_docker_endpoint", lambda: None)
    monkeypatch.setattr(probe.v4, "_container_identity", lambda name: ("same", "same"))
    monkeypatch.setattr(probe.server, "verify_container", lambda *args: None)
    calls = []

    def fake_completion(messages, schema, *, condition, policy, endpoint, model_id):
        calls.append(
            hashlib.sha256(v4.request_bytes(messages, schema, policy, condition)).hexdigest()
        )
        if len(calls) == 1:
            raise TransportError("timeout")
        case_id = probe.ORDER[len(calls) - 1][:4]
        return Completion(_response(case_id), "stop")

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
    assert [row["call"] for row in rows[1:]] == list(probe.ORDER)
    assert calls == [protocol["request_sha256_by_call"][call] for call in probe.ORDER]
    assert rows[1]["error_code"] == "timeout"
    assert rows[2]["finish_reason"] == "stop"
    assert private.stat().st_mode & 0o777 == 0o700
    assert (private / "PC01-N.json.txt").stat().st_mode & 0o777 == 0o600
    verify._journal(output.read_bytes(), "fixed-sha", protocol, cases)
    rows[2]["call"] = "PC01-R"
    changed = ("\n".join(json.dumps(row) for row in rows) + "\n").encode()
    with pytest.raises(verify.VerificationError, match="request identity"):
        verify._journal(changed, "fixed-sha", protocol, cases)


def test_runner_rejects_live_tokenizer_count_drift_before_outputs(tmp_path, monkeypatch):
    protocol = _protocol()
    cases = _cases()
    monkeypatch.setattr(probe, "load_protocol", lambda *args: (protocol, "fixed-sha", cases))
    monkeypatch.setattr(probe, "_token_counts", lambda *args: {call: 101 for call in probe.ORDER})
    monkeypatch.setattr(probe.v4, "_verify_local_docker_endpoint", lambda: None)
    monkeypatch.setattr(probe.v4, "_container_identity", lambda name: ("same", "same"))
    monkeypatch.setattr(probe.server, "verify_container", lambda *args: None)
    output, private = tmp_path / "journal.jsonl", tmp_path / "private"
    monkeypatch.setattr(probe, "JOURNAL", output)
    monkeypatch.setattr(probe, "PRIVATE_DIR", private)
    with pytest.raises(ValueError, match="tokenizer count differs"):
        probe.run(
            argparse.Namespace(
                output=output,
                private_dir=private,
                protocol=tmp_path / "protocol.json",
                model_path=tmp_path / "model.gguf",
                container_name=probe.CONTAINER_NAME,
            )
        )
    assert not output.exists() and not private.exists()


def _replay(tmp_path, monkeypatch, modes=None):
    protocol = _protocol()
    cases = _cases()
    monkeypatch.setattr(verify, "check_protocol", lambda *args: (protocol, "fixed-sha", cases))
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    modes = modes or {}
    rows = [{"event": "header", "protocol_sha256": "fixed-sha"}]
    for call in probe.ORDER:
        mode = modes.get(call, "correct")
        row = {
            "event": "result",
            "call": call,
            "request_sha256": protocol["request_sha256_by_call"][call],
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
            content = _response(call[:4], mode).encode()
            path = private / f"{call}.json.txt"
            path.write_bytes(content)
            path.chmod(0o600)
            row.update(
                finish_reason="stop",
                raw_sha256=hashlib.sha256(content).hexdigest(),
                raw_bytes=len(content),
            )
        rows.append(row)
    journal = tmp_path / "journal.jsonl"
    journal.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    monkeypatch.setattr(verify, "JOURNAL", journal)
    monkeypatch.setattr(verify, "PRIVATE_DIR", private)
    return verify.verify_result(
        tmp_path / "protocol.json", tmp_path / "model.gguf", journal, private
    )


def test_replay_separates_positive_and_negative_gate(tmp_path, monkeypatch):
    result = _replay(tmp_path, monkeypatch)
    assert result["summary"]["calls"] == 6
    assert result["summary"]["contract_pass"] == 6
    assert result["summary"]["positive_B_exact"] == 3
    assert result["summary"]["negative_valid_hold"] == 3
    assert result["candidate_gate_pass"] is True
    assert result["candidate_availability"] == {
        "PC01": {
            "candidate_count_by_arm": {"F": 22, "N": 7, "R": 7},
            "gold_B_candidate_id": "P014",
            "gold_B_display_position_index_base": 1,
            "gold_B_display_position_by_arm": {"F": 14, "N": 5, "R": 3},
            "gold_B_required": True,
        },
        "NC01": {
            "candidate_count_by_arm": {"F": 35, "N": 4, "R": 4},
            "gold_B_candidate_id": None,
            "gold_B_display_position_index_base": 1,
            "gold_B_display_position_by_arm": {"F": None, "N": None, "R": None},
            "gold_B_required": False,
        },
    }
    assert result["full_nominal_pair_comparable_by_case"] == {"PC01": True, "NC01": True}
    assert result["gold_in_requests"] is False
    assert result["official_accuracy_evaluated"] is False


@pytest.mark.parametrize(
    ("call", "mode", "field"),
    [
        ("PC01-N", "wrong_b", "positive_B_exact"),
        ("PC01-N", "wrong_kind", "positive_full_match"),
        ("PC01-R", "null", "positive_full_match"),
        ("NC01-N", "false_nonnull", "negative_valid_hold"),
        ("NC01-R", "extra_key", "negative_valid_hold"),
        ("PC01-N", "illegal_kind", "positive_full_match"),
        ("PC01-R", "whitespace_quote", "positive_full_match"),
    ],
)
def test_candidate_gate_rejects_wrong_or_invalid_answer(tmp_path, monkeypatch, call, mode, field):
    result = _replay(tmp_path, monkeypatch, {call: mode})
    assert result["candidate_gate_pass"] is False
    row = next(item for item in result["per_call"] if item["call"] == call)
    assert row[field] is (
        None if mode in {"extra_key", "illegal_kind", "whitespace_quote"} else False
    )
    if mode == "illegal_kind":
        assert row["contract_error_code"] == "subject_kind_invalid"
    elif mode == "whitespace_quote":
        assert row["contract_error_code"] == "quote_blank_or_invalid"


def test_timeout_is_not_scored_as_semantic_failure(tmp_path, monkeypatch):
    result = _replay(tmp_path, monkeypatch, {"PC01-N": "timeout"})
    assert result["summary"]["transport_or_length_errors"] == 1
    row = next(item for item in result["per_call"] if item["call"] == "PC01-N")
    assert row["positive_B_exact"] is None
    assert row["error_code"] == "timeout"
    assert row["finish_reason"] is None
    assert result["candidate_gate_pass"] is False


@pytest.mark.parametrize("mode", ["timeout", "extra_key"])
def test_full_arm_error_blocks_pair_comparison_but_not_nominal_gate(tmp_path, monkeypatch, mode):
    result = _replay(tmp_path, monkeypatch, {"NC01-F": mode})
    assert result["candidate_gate_pass"] is True
    assert result["full_nominal_pair_comparable_by_case"] == {"PC01": True, "NC01": False}
    row = next(item for item in result["per_call"] if item["call"] == "NC01-F")
    assert row["negative_valid_hold"] is None


def test_alternate_or_existing_output_paths_rejected_before_calls(tmp_path, monkeypatch):
    output, private = tmp_path / "journal.jsonl", tmp_path / "private"
    monkeypatch.setattr(probe, "JOURNAL", output)
    monkeypatch.setattr(probe, "PRIVATE_DIR", private)
    args = argparse.Namespace(
        output=tmp_path / "alternate.jsonl",
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
