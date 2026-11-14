"""Exercise v4 runner safety precedence and private/public output boundaries."""

from __future__ import annotations

import argparse
import json
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.as_safety_v2.transport import Completion, RequestPolicy, TransportError
from experiments.as_safety_v4 import run as runner

MESSAGE = (
    "수리할 로봇청소기 바퀴가 헛돕니다. "
    "탁상 조명에서 연기가 났고, 로봇청소기 전원선에서 불꽃이 튀었습니다."
)
TARGET = {"clause_index": 1, "quote": "로봇청소기"}
CASE = {
    "id": "ES01",
    "user_message": MESSAGE,
    "target": TARGET,
    "expected_route": "safety_action_required",
    "events": [{"gold": "must never enter a prompt"}],
}


def _completion(value: dict, *, finish_reason: str = "stop") -> Completion:
    return Completion(json.dumps(value, ensure_ascii=False), finish_reason)


def _event(quote: str, occurrence: str = "observed") -> dict:
    return {"event_span": {"clause_index": 2, "quote": quote}, "occurrence": occurrence}


def _owner(quote: str, relation: str) -> dict:
    return {
        "hazard_owner_span": {"clause_index": 2, "quote": quote},
        "owner_to_target": relation,
    }


def test_two_events_keep_current_hazard_immediate_and_raw_private(tmp_path) -> None:
    replies = iter(
        [
            _completion(
                {
                    "events": [_event("연기가 났고"), _event("불꽃이 튀었습니다")],
                    "overflow": False,
                }
            ),
            _completion(_owner("탁상 조명", "other")),
            _completion(_owner("로봇청소기 전원선", "current")),
        ]
    )
    requests = []

    def fake(messages, schema, *, policy):
        requests.append((messages, schema, policy))
        return next(replies)

    result = runner.call_case(CASE, RequestPolicy(), tmp_path, completion_call=fake)
    assert result["route"] == "safety_action_required"
    assert result["request_count"] == 3
    assert [stage["owner_to_target"] for stage in result["stage2"]] == ["other", "current"]
    assert result["stage1"]["status"] == "validated"
    assert "quote" not in result["stage1"]["events"][0]["event_span"]
    assert "must never enter a prompt" not in json.dumps(requests, ensure_ascii=False, default=str)
    assert (
        "탁상 조명"
        not in requests[2][0][1]["content"].split("위험 사건 후보:")[1].split("발생 판단 후보:")[0]
    )
    for path in tmp_path.iterdir():
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "ES01-stage1.json.txt",
        "ES01-stage2-1.json.txt",
        "ES01-stage2-2.json.txt",
    ]
    assert "불꽃이 튀었습니다" not in json.dumps(result, ensure_ascii=False)
    gold = dict(
        CASE,
        events=[
            {**_event("연기가 났고"), **_owner("탁상 조명", "other")},
            {**_event("불꽃이 튀었습니다"), **_owner("로봇청소기 전원선", "current")},
        ],
    )
    summary = runner.summarize([result], [gold])
    assert summary["stage1_exact_event_cases"] == 1
    assert summary["actionable_gold_on_exact_event_cases"] == 2
    assert summary["relation_correct_on_exact_event_cases"] == 2
    assert summary["route_correct"] == 1
    assert summary["request_count"] == 3
    assert summary["case_elapsed_p50_ms"] == result["elapsed_ms"]
    assert result["model_call_latency_sum_ms"] >= 0
    for stage in [result["stage1"], *result["stage2"]]:
        assert stage["request_latency_ms"] is not None
        assert stage["latency_ms"] >= stage["request_latency_ms"]
    assert result["model_call_latency_sum_ms"] == round(
        result["stage1"]["request_latency_ms"]
        + sum(stage["request_latency_ms"] for stage in result["stage2"]),
        3,
    )


def test_stage1_contract_error_fails_closed_without_stage2(tmp_path) -> None:
    count = 0

    def fake(messages, schema, *, policy):
        nonlocal count
        count += 1
        return Completion('{"events":[],"overflow":false,"events":[]}', "stop")

    result = runner.call_case(CASE, RequestPolicy(), tmp_path, completion_call=fake)
    assert count == 1
    assert result["route"] == "confirming_safety_status"
    assert result["stage1"]["status"] == "contract_error"
    assert result["stage1"]["error_code"] == "duplicate_key"
    assert result["stage2"] == []


def test_stage2_transport_error_does_not_hide_confirmed_current_hazard(tmp_path) -> None:
    replies = iter(
        [
            _completion(
                {
                    "events": [_event("연기가 났고"), _event("불꽃이 튀었습니다")],
                    "overflow": False,
                }
            ),
            _completion(_owner("로봇청소기 전원선", "current")),
        ]
    )
    calls = 0

    def fake(messages, schema, *, policy):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise TransportError("network_error")
        return next(replies)

    result = runner.call_case(CASE, RequestPolicy(), tmp_path, completion_call=fake)
    assert result["route"] == "safety_action_required"
    assert result["stage2"][1]["status"] == "response_error"
    assert result["stage2"][1]["error_code"] == "network_error"
    assert result["request_count"] == 3
    assert not (tmp_path / "ES01-stage2-2.json.txt").exists()


@pytest.mark.parametrize(
    ("stage2_payload", "error_code", "error_field"),
    [
        (_owner("탁상 조명", "same"), "relation_invalid", "owner_to_target"),
        ({**_owner("탁상 조명", "other"), "unexpected": True}, "fields_invalid", "stage2"),
        (
            {"hazard_owner_span": {"clause_index": 2, "quote": "   "}, "owner_to_target": "other"},
            "quote_blank",
            "hazard_owner_span",
        ),
    ],
)
def test_stage2_contract_error_confirms_without_retry(
    tmp_path, stage2_payload: dict, error_code: str, error_field: str
) -> None:
    replies = iter(
        [
            _completion({"events": [_event("연기가 났고")], "overflow": False}),
            _completion(stage2_payload),
        ]
    )
    calls = 0

    def fake(messages, schema, *, policy):
        nonlocal calls
        calls += 1
        return next(replies)

    result = runner.call_case(CASE, RequestPolicy(), tmp_path, completion_call=fake)
    assert calls == result["request_count"] == 2
    assert result["stage1"]["status"] == "validated"
    assert result["stage2"][0]["status"] == "contract_error"
    assert result["stage2"][0]["error_code"] == error_code
    assert result["stage2"][0]["error_field"] == error_field
    assert result["stage2"][0]["called"] is True
    assert result["route"] == "confirming_safety_status"


def test_nonoccurring_event_skips_owner_call(tmp_path) -> None:
    def fake(messages, schema, *, policy):
        return _completion(
            {
                "events": [_event("연기가 났고", "nonoccurring")],
                "overflow": False,
            }
        )

    result = runner.call_case(CASE, RequestPolicy(), tmp_path, completion_call=fake)
    assert result["route"] == "collecting_service_request"
    assert result["request_count"] == 1
    assert result["stage2"][0]["skip_reason"] == "nonoccurring"
    assert result["stage2"][0]["called"] is False


def test_finish_length_keeps_raw_but_confirms(tmp_path) -> None:
    def fake(messages, schema, *, policy):
        return _completion({"events": [], "overflow": False}, finish_reason="length")

    result = runner.call_case(CASE, RequestPolicy(), tmp_path, completion_call=fake)
    assert result["route"] == "confirming_safety_status"
    assert result["stage1"]["status"] == "response_error"
    assert result["stage1"]["error_code"] == "finish_length"
    assert (tmp_path / "ES01-stage1.json.txt").exists()


def test_existing_output_is_not_resumed_or_overwritten(tmp_path) -> None:
    output = tmp_path / "journal.jsonl"
    output.write_text("partial\n", encoding="utf-8")
    args = argparse.Namespace(
        output=output,
        private_dir=tmp_path / "private",
        protocol=tmp_path / "missing-protocol.json",
        model_path=tmp_path / "missing-model.gguf",
        container_name="not-started",
    )
    with pytest.raises(FileExistsError, match="never overwrite"):
        runner.run(args)
    assert output.read_text(encoding="utf-8") == "partial\n"


def test_private_file_mode_is_exact_even_with_restrictive_umask(tmp_path) -> None:
    path = tmp_path / "raw.json.txt"
    previous = runner.os.umask(0o777)
    try:
        runner._raw(path, "{}")
    finally:
        runner.os.umask(previous)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_private_directory_mode_is_exact_even_with_restrictive_umask(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        runner,
        "load_protocol",
        lambda protocol, model: ({"request_policy": runner.REQUEST}, "a" * 64),
    )
    monkeypatch.setattr(runner, "load_cases", lambda dataset: [])
    monkeypatch.setattr(runner, "verify_container", lambda name, model: None)
    monkeypatch.setattr(runner, "CASE_ORDER", ())
    args = argparse.Namespace(
        output=tmp_path / "journal.jsonl",
        private_dir=tmp_path / "private",
        protocol=tmp_path / "protocol.json",
        model_path=tmp_path / "model.gguf",
        container_name="unused",
    )
    previous = runner.os.umask(0o777)
    try:
        runner.run(args)
    finally:
        runner.os.umask(previous)
    assert stat.S_IMODE(args.private_dir.stat().st_mode) == 0o700


def _frozen_protocol_fixture(tmp_path: Path, monkeypatch) -> tuple[Path, Path, dict]:
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    paths = {
        "dataset": tmp_path / "dataset.json",
        "review": tmp_path / "review.md",
        "field_review": tmp_path / "field-review.md",
        "method": tmp_path / "method.md",
    }
    for key, path in paths.items():
        path.write_text(key, encoding="utf-8")
    monkeypatch.setattr(runner, "INPUTS", paths)
    sources = set(runner.REQUIRED_V4_SOURCES)
    for relative in sources:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")
    monkeypatch.setattr(runner, "_source_paths", lambda commit: sources)
    monkeypatch.setattr(
        runner, "_committed", lambda commit, relative: (tmp_path / relative).read_bytes()
    )
    monkeypatch.setattr(runner, "digest_file", lambda path: runner.MODEL_SHA)
    protocol = {
        "kind": runner.KIND,
        "claim_scope": runner.SCOPE,
        "case_order": list(runner.CASE_ORDER),
        "frozen_code_commit": "a" * 40,
        "input_hashes": {key: runner.digest(path.read_bytes()) for key, path in paths.items()},
        "source_manifest": {
            relative: runner.digest((tmp_path / relative).read_bytes()) for relative in sources
        },
        "model_sha256": runner.MODEL_SHA,
        "server_image_digest": runner.IMAGE,
        "request_policy": runner.REQUEST,
        "local_runtime": runner.RUNTIME,
        "retry_policy": "no_retry_manual_audit_on_interruption",
        "private_output": "outside_repository_mode_0700_files_0600",
    }
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol), encoding="utf-8")
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")
    return path, model, protocol


def test_preflight_rejects_missing_required_verifier_source(tmp_path, monkeypatch) -> None:
    path, model, _ = _frozen_protocol_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        runner,
        "_source_paths",
        lambda commit: runner.REQUIRED_V4_SOURCES - {"experiments/as_safety_v4/verify.py"},
    )
    with pytest.raises(ValueError, match="required v4 source missing"):
        runner.load_protocol(path, model)


def test_preflight_rejects_untracked_checkout(tmp_path, monkeypatch) -> None:
    path, model, _ = _frozen_protocol_fixture(tmp_path, monkeypatch)

    def fake_git(*args):
        if args[0] == "show":
            return path.read_bytes()
        if args == ("status", "--porcelain"):
            return b"?? untracked-source.py\n"
        raise AssertionError(args)

    monkeypatch.setattr(runner, "_git", fake_git)
    with pytest.raises(ValueError, match="checkout differs"):
        runner.load_protocol(path, model)


@pytest.mark.parametrize("invalid_field", ["port", "mount"])
def test_container_preflight_rejects_wrong_port_or_mount(
    tmp_path, monkeypatch, invalid_field: str
) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")
    observed = {
        "State": {"Running": True},
        "Image": runner.IMAGE,
        "HostConfig": {
            "NanoCpus": 2_000_000_000,
            "Memory": runner.RUNTIME["memory_bytes"],
            "PortBindings": {"8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18081"}]},
        },
        "Config": {"Cmd": runner.SERVER_ARGS},
        "Mounts": [
            {
                "Source": str(model.resolve()),
                "Destination": "/models/kanana.gguf",
                "RW": False,
            }
        ],
    }
    if invalid_field == "port":
        observed["HostConfig"]["PortBindings"]["8080/tcp"][0]["HostPort"] = "18082"
    else:
        observed["Mounts"][0]["RW"] = True
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps([observed])),
    )
    with pytest.raises(ValueError, match="model (server port|mount) differs"):
        runner.verify_container("model", model)
