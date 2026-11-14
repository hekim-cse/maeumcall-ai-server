"""Independent replay catches altered model evidence and public decisions."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.transport import Completion, RequestPolicy, TransportError
from experiments.as_safety_v4 import run as candidate_runner
from experiments.as_safety_v4 import verify

MESSAGE = "접수할 전기포트가 고장났습니다. 토스터에서 불꽃이 났습니다."
CASE = {
    "id": "ES01",
    "user_message": MESSAGE,
    "target": {"clause_index": 1, "quote": "전기포트"},
    "events": [{
        "event_span": {"clause_index": 2, "quote": "불꽃이 났습니다"},
        "occurrence": "observed",
        "hazard_owner_span": {"clause_index": 2, "quote": "토스터"},
        "owner_to_target": "other",
    }],
    "expected_route": "collecting_service_request",
}


def _public(index: int, quote: str) -> dict:
    span = anchor_span({"clause_index": index, "quote": quote}, split_clauses(MESSAGE), field="x")
    assert span is not None
    return {key: span[key] for key in verify.SPAN_KEYS}


def _raw(directory: Path, name: str, value: dict) -> tuple[str, int]:
    encoded = json.dumps(value, ensure_ascii=False).encode("utf-8")
    path = directory / name
    path.write_bytes(encoded)
    os.chmod(path, 0o600)
    return hashlib.sha256(encoded).hexdigest(), len(encoded)


def _row(directory: Path) -> dict:
    one_sha, one_size = _raw(directory, "ES01-stage1.json.txt", {
        "events": [{
            "event_span": {"clause_index": 2, "quote": "불꽃이 났습니다"},
            "occurrence": "observed",
        }],
        "overflow": False,
    })
    two_sha, two_size = _raw(directory, "ES01-stage2-1.json.txt", {
        "hazard_owner_span": {"clause_index": 2, "quote": "토스터"},
        "owner_to_target": "other",
    })
    return {
        "event": "end", "case_id": "ES01",
        "stage1": {
            "called": True, "status": "validated", "skip_reason": None,
            "error_code": None, "error_field": None, "finish_reason": "stop",
            "latency_ms": 1.0, "request_latency_ms": 1.0,
            "raw_sha256": one_sha, "raw_bytes": one_size,
            "events": [{"event_span": _public(2, "불꽃이 났습니다"), "occurrence": "observed"}],
            "overflow": False,
        },
        "stage2": [{
            "called": True, "status": "validated", "skip_reason": None,
            "error_code": None, "error_field": None, "finish_reason": "stop",
            "latency_ms": 2.0, "request_latency_ms": 2.0,
            "raw_sha256": two_sha, "raw_bytes": two_size,
            "event_index": 1, "owner_to_target": "other",
            "hazard_owner_span": _public(2, "토스터"),
        }],
        "route": "collecting_service_request", "request_count": 2,
        "model_call_latency_sum_ms": 3.0, "elapsed_ms": 3.5,
    }


def test_replay_raw_source_and_summary(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    row = _row(directory)
    result = verify.audit_end(row, CASE, directory)
    assert result["route"] == "collecting_service_request"
    summary = verify.summarize([result], [CASE])
    assert summary["route_correct"] == 1
    assert summary["stage1_exact_event_cases"] == 1
    assert summary["relation_correct_on_exact_event_cases"] == 1
    assert summary["actionable_gold_on_exact_event_cases"] == 1
    assert summary["false_direct_other"] == 0


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("route",), "safety_action_required"),
        (("request_count",), 1),
        (("model_call_latency_sum_ms",), 2.0),
        (("stage1", "events", 0, "occurrence"), "uncertain"),
        (("stage2", 0, "owner_to_target"), "current"),
        (("stage2", 0, "raw_sha256"), "0" * 64),
        (("stage2", 0, "request_latency_ms"), 3.0),
    ],
)
def test_replay_rejects_public_tampering(tmp_path: Path, path: tuple, value: object) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    row = copy.deepcopy(_row(directory))
    item = row
    for key in path[:-1]:
        item = item[key]
    item[path[-1]] = value
    with pytest.raises(ValueError):
        verify.audit_end(row, CASE, directory)


def test_replay_rejects_private_raw_tampering(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    row = _row(directory)
    (directory / "ES01-stage2-1.json.txt").write_text('{"owner_to_target":"current"}')
    with pytest.raises(ValueError, match="private raw response differs"):
        verify.audit_end(row, CASE, directory)


def test_replay_rejects_private_file_exposure(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    row = _row(directory)
    os.chmod(directory / "ES01-stage1.json.txt", 0o644)
    with pytest.raises(ValueError, match="private raw metadata differs"):
        verify.audit_end(row, CASE, directory)


def test_replay_matches_runner_output_without_importing_runner_in_verifier(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    responses = iter([
        Completion(content=json.dumps({
            "events": [{
                "event_span": {"clause_index": 2, "quote": "불꽃이 났습니다"},
                "occurrence": "observed",
            }],
            "overflow": False,
        }, ensure_ascii=False), finish_reason="stop"),
        Completion(content=json.dumps({
            "hazard_owner_span": {"clause_index": 2, "quote": "토스터"},
            "owner_to_target": "other",
        }, ensure_ascii=False), finish_reason="stop"),
    ])

    def complete(_messages, _schema, *, policy):
        assert isinstance(policy, RequestPolicy)
        return next(responses)

    row = candidate_runner.call_case(CASE, RequestPolicy(), directory, completion_call=complete)
    audited = verify.audit_end(row, CASE, directory)
    assert audited["route"] == row["route"]
    assert verify.summarize([audited], [CASE]) == {
        "event": "summary", **candidate_runner.summarize([row], [CASE])
    }


def test_replay_recomputes_contract_error_code(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    raw = b'{"events":[],"events":[],"overflow":false}'
    path = directory / "ES01-stage1.json.txt"
    path.write_bytes(raw)
    os.chmod(path, 0o600)
    row = {
        "event": "end", "case_id": "ES01",
        "stage1": {
            "called": True, "status": "contract_error", "skip_reason": None,
            "error_code": "duplicate_key", "error_field": "$", "finish_reason": "stop",
            "latency_ms": 1.0, "request_latency_ms": 0.5,
            "raw_sha256": hashlib.sha256(raw).hexdigest(), "raw_bytes": len(raw),
            "events": None, "overflow": None,
        },
        "stage2": [], "route": "confirming_safety_status", "request_count": 1,
        "model_call_latency_sum_ms": 0.5, "elapsed_ms": 1.2,
    }
    assert verify.audit_end(row, CASE, directory)["stage1_valid"] is False
    row["stage1"]["error_code"] = "invalid_json"
    with pytest.raises(ValueError, match="contract error differs"):
        verify.audit_end(row, CASE, directory)


@pytest.mark.parametrize("raw", [b"", b"  \n"])
def test_replay_rejects_blank_private_response(tmp_path: Path, raw: bytes) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    row = _row(directory)
    path = directory / "ES01-stage1.json.txt"
    path.write_bytes(raw)
    row["stage1"]["raw_sha256"] = hashlib.sha256(raw).hexdigest()
    row["stage1"]["raw_bytes"] = len(raw)
    with pytest.raises(ValueError, match="private raw metadata differs|private raw content blank"):
        verify.audit_end(row, CASE, directory)


def test_protocol_requires_matching_model_file(tmp_path: Path) -> None:
    protocol = {
        "kind": verify.KIND,
        "claim_scope": verify.SCOPE,
        "case_order": list(verify.CASE_ORDER),
        "frozen_code_commit": "0" * 40,
        "input_hashes": {},
        "source_manifest": {},
        "model_sha256": verify.MODEL_SHA,
        "server_image_digest": verify.IMAGE,
        "request_policy": verify.POLICY,
        "local_runtime": verify.RUNTIME,
        "retry_policy": "no_retry_manual_audit_on_interruption",
        "private_output": "outside_repository_mode_0700_files_0600",
    }
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol))
    model_path = tmp_path / "model.gguf"
    model_path.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="model digest differs"):
        verify.check_protocol(protocol_path, model_path)


def test_replay_accepts_finite_transport_error_without_raw(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)

    def fail(_messages, _schema, *, policy):
        assert isinstance(policy, RequestPolicy)
        raise TransportError("network_error")

    row = candidate_runner.call_case(CASE, RequestPolicy(), directory, completion_call=fail)
    assert row["stage1"]["status"] == "response_error"
    assert list(directory.iterdir()) == []
    assert verify.audit_end(row, CASE, directory)["route"] == "confirming_safety_status"
    row["stage1"]["error_code"] = "arbitrary"
    with pytest.raises(ValueError, match="transport result differs"):
        verify.audit_end(row, CASE, directory)
