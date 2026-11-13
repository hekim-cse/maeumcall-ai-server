"""Preflight and journal boundaries for the conditional Stage2 diagnostic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.transport import Completion, RequestPolicy, TransportError
from experiments.as_safety_v3 import run as runner

MESSAGE = "접수할 전기포트에서 불꽃이 났습니다."


def _case() -> tuple[dict, dict]:
    clauses = split_clauses(MESSAGE)
    stage1 = {
        "event_span": anchor_span(
            {"clause_index": 1, "quote": "불꽃"}, clauses, field="event_span"
        ),
        "subject_span": anchor_span(
            {"clause_index": 1, "quote": "전기포트"}, clauses, field="subject_span"
        ),
        "owner_span": anchor_span(
            {"clause_index": 1, "quote": "전기포트"}, clauses, field="owner_span"
        ),
        "owner_kind": "explicit",
    }
    case = {
        "id": "RE01",
        "user_message": MESSAGE,
        "target": {"clause_index": 1, "quote": "전기포트"},
    }
    return case, stage1


def _protocol(root: Path, input_bytes: bytes, source_bytes: bytes) -> tuple[Path, Path]:
    input_path = root / "input.json"
    input_path.write_bytes(input_bytes)
    for relative in runner.REQUIRED_V3_SOURCES:
        source_path = root / relative
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(source_bytes)
    model_path = root / "model.gguf"
    model_path.write_bytes(b"model")
    payload = {
        "kind": runner.KIND,
        "claim_scope": runner.SCOPE,
        "case_order": runner.CASE_ORDER,
        "frozen_code_commit": "a" * 40,
        "input_hashes": {"input": runner.digest(input_bytes)},
        "source_manifest": {
            relative: runner.digest(source_bytes) for relative in runner.REQUIRED_V3_SOURCES
        },
        "model_sha256": runner.MODEL_SHA,
        "server_image_digest": runner.IMAGE,
        "request_policy": runner.REQUEST,
        "local_runtime": runner.RUNTIME,
        "retry_policy": "no_retry_manual_audit_on_interruption",
        "private_output": "outside_repository_mode_0700_files_0600",
    }
    protocol_path = root / "protocol.json"
    protocol_path.write_text(json.dumps(payload), encoding="utf-8")
    return protocol_path, model_path


def test_protocol_preflight_rejects_input_source_and_checkout_drift(tmp_path, monkeypatch):
    root = tmp_path
    protocol_path, model_path = _protocol(root, b"input", b"source")
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "INPUTS", {"input": root / "input.json"})
    monkeypatch.setattr(runner, "digest_file", lambda _: runner.MODEL_SHA)
    monkeypatch.setattr(runner, "_source_paths", lambda _: set(runner.REQUIRED_V3_SOURCES))
    committed = {"input.json": b"input"} | {
        relative: b"source" for relative in runner.REQUIRED_V3_SOURCES
    }
    monkeypatch.setattr(runner, "_committed", lambda _, path: committed[path])
    monkeypatch.setattr(
        runner,
        "_git",
        lambda *args: protocol_path.read_bytes() if args[0] == "show" else b"",
    )
    runner.load_protocol(protocol_path, model_path)

    (root / "input.json").write_bytes(b"changed")
    with pytest.raises(ValueError, match="frozen input differs"):
        runner.load_protocol(protocol_path, model_path)
    (root / "input.json").write_bytes(b"input")

    (root / "experiments/as_safety_v3/run.py").write_bytes(b"changed")
    with pytest.raises(ValueError, match="frozen source differs"):
        runner.load_protocol(protocol_path, model_path)
    (root / "experiments/as_safety_v3/run.py").write_bytes(b"source")

    monkeypatch.setattr(
        runner,
        "_git",
        lambda *args: protocol_path.read_bytes() if args[0] == "show" else b"dirty",
    )
    with pytest.raises(ValueError, match="tracked checkout differs"):
        runner.load_protocol(protocol_path, model_path)


def test_protocol_rejects_old_commit_without_required_v3_source(tmp_path, monkeypatch):
    protocol_path, model_path = _protocol(tmp_path, b"input", b"source")
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "INPUTS", {"input": tmp_path / "input.json"})
    monkeypatch.setattr(runner, "digest_file", lambda _: runner.MODEL_SHA)
    monkeypatch.setattr(runner, "_committed", lambda *_: b"input")
    missing = runner.REQUIRED_V3_SOURCES - {"experiments/as_safety_v3/verify.py"}
    monkeypatch.setattr(runner, "_source_paths", lambda _: missing)
    with pytest.raises(ValueError, match="required v3 source missing"):
        runner.load_protocol(protocol_path, model_path)


def test_call_case_records_only_hash_and_public_span(tmp_path, monkeypatch):
    case, stage1 = _case()
    raw = json.dumps(
        {
            "owner_to_target": "same",
            "hazard_owner_span": {"clause_index": 1, "quote": "전기포트"},
        },
        ensure_ascii=False,
    )
    monkeypatch.setattr(
        runner, "post_json_completion", lambda *_args, **_kwargs: Completion(raw, "stop")
    )
    result = runner.call_case(case, {"status": "validated"}, stage1, RequestPolicy(), tmp_path)
    stage2 = result["stage2"]
    assert stage2["status"] == "validated"
    assert stage2["model_link"] == "same"
    assert result["source_relation"] == "current"
    assert stage2["raw_sha256"] == runner.digest(raw.encode())
    assert stage2["hazard_owner_span"] == runner._public_span(stage1["owner_span"])
    assert "quote" not in stage2["hazard_owner_span"]
    assert "전기포트" not in json.dumps(result, ensure_ascii=False)
    assert (tmp_path / "RE01-stage2.json.txt").stat().st_mode & 0o077 == 0


def test_call_case_keeps_errors_and_skips_without_retry(tmp_path, monkeypatch):
    case, stage1 = _case()
    calls = 0

    def failed(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise TransportError("timeout")

    monkeypatch.setattr(runner, "post_json_completion", failed)
    error = runner.call_case(case, {}, stage1, RequestPolicy(), tmp_path)
    assert error["stage2"]["status"] == "response_error"
    assert error["stage2"]["error_code"] == "timeout"
    assert error["source_relation"] == "unknown"
    skipped = runner.call_case(case, {}, None, RequestPolicy(), tmp_path)
    assert skipped["stage2"]["status"] == "skipped"
    assert skipped["stage2"]["skip_reason"] == "baseline_stage1_invalid"
    assert calls == 1


@pytest.mark.parametrize(
    ("payload", "expected_code", "expected_field"),
    [
        (
            {
                "owner_to_target": "invented",
                "hazard_owner_span": {"clause_index": 1, "quote": "전기포트"},
            },
            "link_invalid",
            "owner_to_target",
        ),
        (
            {
                "owner_to_target": "same",
                "hazard_owner_span": {"clause_index": 1, "quote": "전기포트"},
                "extra": "ignored",
            },
            "fields_invalid",
            "stage2",
        ),
        (
            {
                "owner_to_target": "same",
                "hazard_owner_span": {"clause_index": 1, "quote": " 전기포트"},
            },
            "quote_blank",
            "hazard_owner_span",
        ),
    ],
)
def test_call_case_records_contract_errors_without_retry(
    tmp_path, monkeypatch, payload, expected_code, expected_field
):
    case, stage1 = _case()
    raw = json.dumps(payload, ensure_ascii=False)
    calls = []

    def complete(*_args, **_kwargs):
        calls.append(True)
        return Completion(raw, "stop")

    monkeypatch.setattr(runner, "post_json_completion", complete)
    result = runner.call_case(case, {"status": "validated"}, stage1, RequestPolicy(), tmp_path)
    stage2 = result["stage2"]
    assert len(calls) == 1
    assert stage2["status"] == "contract_error"
    assert (stage2["error_code"], stage2["error_field"]) == (expected_code, expected_field)
    assert stage2["raw_sha256"] == runner.digest(raw.encode("utf-8"))
    assert stage2["raw_bytes"] == len(raw.encode("utf-8"))
    assert result["source_relation"] == "unknown"
    assert (tmp_path / "RE01-stage2.json.txt").read_text(encoding="utf-8") == raw


def test_baseline_replay_rejects_private_raw_mismatch(tmp_path, monkeypatch):
    baseline_protocol = tmp_path / "baseline-protocol.json"
    baseline_protocol.write_bytes(b"baseline")
    baseline_journal = tmp_path / "baseline-journal.jsonl"
    private_dir = tmp_path / "old-private"
    private_dir.mkdir(mode=0o700)
    monkeypatch.setattr(runner, "BASELINE_PROTOCOL", baseline_protocol)
    monkeypatch.setattr(runner, "BASELINE_JOURNAL", baseline_journal)
    monkeypatch.setattr(
        runner,
        "load_development_cases",
        lambda **_: [
            {
                "id": case_id,
                "user_message": f"message-{case_id}",
                "target": {"clause_index": 1, "quote": "접수 대상"},
            }
            for case_id in runner.CASE_IDS
        ],
    )
    span = {
        "clause_index": 1,
        "quote": "불꽃",
        "start": 0,
        "end": 2,
        "quote_sha256": runner.digest("불꽃".encode()),
    }
    validated = {
        "event_span": span,
        "subject_span": span,
        "owner_span": span,
        "owner_kind": "explicit",
    }

    def validate(_raw, message, **_args):
        if message.endswith(("RE01", "RE02")):
            raise ValidationError("quote_unanchored", "owner_span")
        return validated

    monkeypatch.setattr(runner, "validate_stage1", validate)
    rows = [{"event": "header", "protocol_sha256": runner.digest(b"baseline")}]
    for case_id in runner.CASE_IDS:
        raw_path = private_dir / f"{case_id}-stage1.json.txt"
        raw_path.write_bytes(b"raw")
        raw_path.chmod(0o600)
        failed = case_id in {"RE01", "RE02"}
        first = {
            "called": True,
            "status": "contract_error" if failed else "validated",
            "finish_reason": "stop",
            "raw_sha256": runner.digest(b"raw"),
            "raw_bytes": 3,
            "error_code": "quote_unanchored" if failed else None,
            "error_field": "owner_span" if failed else None,
            "spans": None
            if failed
            else {
                name: runner._public_span(validated[name])
                for name in ("event_span", "subject_span", "owner_span")
            },
            "owner_kind": None if failed else "explicit",
        }
        rows.extend(
            [
                {"event": "begin", "case_id": case_id},
                {"event": "end", "case_id": case_id, "stage1": first},
            ]
        )
    baseline_journal.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    assert sum(value is not None for _, _, value in runner.load_baseline(private_dir)) == 20
    (private_dir / "V01-stage1.json.txt").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="baseline Stage1 raw differs"):
        runner.load_baseline(private_dir)


def test_baseline_rejects_private_directory_inside_repository(tmp_path, monkeypatch):
    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="outside repository"):
        runner.load_baseline(private_dir)


def test_run_uses_explicit_frozen_request_policy(tmp_path, monkeypatch):
    output = tmp_path / "journal.jsonl"
    private_dir = tmp_path / "new-private"
    old_private = tmp_path / "old-private"
    monkeypatch.setattr(
        runner,
        "load_protocol",
        lambda *_: ({"request_policy": runner.REQUEST}, "f" * 64),
    )
    monkeypatch.setattr(
        runner,
        "load_baseline",
        lambda _: [({"id": "RE01"}, {"status": "contract_error"}, None)],
    )
    monkeypatch.setattr(runner, "verify_container", lambda *_: None)
    observed = []

    def capture(_case, _first, _validated, policy, _private_dir):
        observed.append(policy)
        return {"event": "end", "case_id": "RE01"}

    monkeypatch.setattr(runner, "call_case", capture)
    args = argparse.Namespace(
        output=output,
        private_dir=private_dir,
        baseline_private_dir=old_private,
        protocol=tmp_path / "protocol.json",
        model_path=tmp_path / "model.gguf",
        container_name="fake",
    )
    runner.run(args)
    assert len(observed) == 1
    assert observed[0].max_tokens == runner.REQUEST["max_tokens"]
    assert observed[0].stop == tuple(runner.REQUEST["stop"])
    assert observed[0].seed == runner.REQUEST["seed"]


def test_run_rejects_existing_output_before_model_preflight(tmp_path, monkeypatch):
    output = tmp_path / "journal.jsonl"
    output.write_text("interrupted", encoding="utf-8")
    monkeypatch.setattr(
        runner,
        "load_protocol",
        lambda *_: pytest.fail("preflight must not run after interruption"),
    )
    args = argparse.Namespace(output=output, private_dir=tmp_path / "new-private")
    with pytest.raises(FileExistsError, match="manual audit"):
        runner.run(args)
