from __future__ import annotations

import json
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from experiments.internal_validation_pf_sentinel_v1 import gate, worker
from experiments.internal_validation_pf_sentinel_v1 import run as pf_run
from experiments.internal_validation_pf_sentinel_v1 import verify as pf_verify
from experiments.internal_validation_pf_sentinel_v1.verify import summarize


def state(safe: bool) -> dict:
    if safe:
        return {
            "conversation_state": "safety_action_required",
            "workflow_status": "blocked",
            "safety_status": "safety_issue",
            "error_type": None,
        }
    return {
        "conversation_state": "collecting_service_request",
        "workflow_status": "in_progress",
        "safety_status": None,
        "error_type": None,
    }


def test_pf_gate_separates_new_miss_preexisting_miss_recovery_and_false_alarm():
    baseline = {case_id: state(False) for case_id in gate.IDS}
    candidate = {case_id: state(False) for case_id in gate.IDS}
    baseline[gate.IDS[0]] = state(True)
    baseline[gate.IDS[2]] = state(True)
    candidate[gate.IDS[2]] = state(True)
    candidate[gate.IDS[3]] = state(True)
    candidate[gate.IDS[8]] = state(True)
    summary = summarize({"baseline": baseline, "candidate": candidate})
    assert summary["new_direct_danger_misses"] == [gate.IDS[0]]
    assert gate.IDS[1] in summary["preexisting_direct_danger_misses"]
    assert summary["recovered_direct_danger_hits"] == [gate.IDS[3]]
    assert summary["retained_direct_danger_hits"] == [gate.IDS[2]]
    assert summary["new_false_alarms"] == [gate.IDS[8]]
    assert summary["direct_danger_denominator"] == 8
    assert summary["negative_denominator"] == 8


def test_pf_gate_rejects_invalid_safety_state_and_graph_error():
    projections = {
        arm: {case_id: state(False) for case_id in gate.IDS}
        for arm in ("baseline", "candidate")
    }
    projections["candidate"][gate.IDS[0]] = {
        **state(True), "workflow_status": "in_progress"
    }
    with pytest.raises(ValueError, match="safety route"):
        summarize(projections)
    projections["candidate"][gate.IDS[0]] = {
        **state(False), "error_type": "AIResponseValidationError"
    }
    with pytest.raises(ValueError, match="graph error"):
        summarize(projections)


def test_pf_private_raw_replay_detects_tampering(tmp_path):
    private = tmp_path / "raw"
    private.mkdir(mode=0o700)
    path = worker._raw_path(private, "baseline", gate.IDS[0], 0)
    record = worker._save(path, json.dumps({"answer": "안전"}, ensure_ascii=False))
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert worker._read(path, record) == '{"answer": "안전"}'
    path.write_text("altered", encoding="utf-8")
    with pytest.raises(ValueError, match="response differs"):
        worker._read(path, record)


def test_pf_worker_replays_saved_completion_without_http(tmp_path, monkeypatch):
    from scripts import probe_nlu_safety_graph, run_ai_heldout_pair

    private = tmp_path / "raw"
    private.mkdir(mode=0o700)
    monkeypatch.setattr(worker, "_frozen_arm", lambda *_args: None)
    live_calls = []

    def fake_http(_endpoint, _model_id, _messages, _policy):
        live_calls.append(True)
        return '{"answer":"ok"}'

    def fake_graph(case, *, endpoint, model_id, policy, completion_post):
        assert model_id == "kanana-q5"
        raw = completion_post(endpoint, model_id, [{"role": "user", "content": case.user_message}], policy)
        assert raw == '{"answer":"ok"}'
        return {
            "case_id": case.id,
            "model_request_count": 1,
            "attempts": [{"latency_ms": 12.5, "contract_valid": True}],
            "conversation_state": "collecting_service_request",
            "workflow_status": "in_progress",
            "safety_status": None,
            "error_type": None,
        }

    monkeypatch.setattr(run_ai_heldout_pair, "_post_completion", fake_http)
    monkeypatch.setattr(probe_nlu_safety_graph, "run_graph_case", fake_graph)
    payload = {
        "mode": "live", "arm": "baseline", "arm_root": str(Path(__file__).resolve().parents[1]),
        "commit": "ignored", "head": "ignored", "manifest": {},
        "case_id": gate.IDS[0], "private_dir": str(private),
        "request_policy": {
            "endpoint": "http://127.0.0.1:18081/v1/chat/completions",
            "model_id": "kanana-q5",
        },
        "raw_attempts": [],
    }
    live = worker.one_case(payload)
    assert live_calls == [True]
    assert live["projection"]["attempts"] == [{"contract_valid": True}]
    monkeypatch.setattr(
        run_ai_heldout_pair, "_post_completion",
        lambda *_args: pytest.fail("replay called HTTP"),
    )
    replay = worker.one_case({**payload, "mode": "replay", "raw_attempts": live["raw_attempts"]})
    assert replay == live


def test_real_git_pf_protocol_32_arm_raw_replay_with_fake_transport(monkeypatch, tmp_path):
    """Use real Git, graph workers and replay; substitute only Docker and HTTP."""
    from experiments.internal_validation_pair_v1 import qualification as validation_gate

    root = validation_gate.ROOT
    fake_site = tmp_path / "fake_site"
    fake_site.mkdir()
    raw = json.dumps(
        {
            "intent": "service_request",
            "fields": {
                "product_type": None, "model_name": None, "symptom": None,
                "occurred_at": None, "safety_status": None,
                "service_channel": None, "preferred_schedule": None,
            },
            "user_action": "unknown",
            "change_field": None,
        },
        ensure_ascii=False,
    )
    body = json.dumps({"choices": [{"message": {"content": raw}}]}, ensure_ascii=False)
    (fake_site / "sitecustomize.py").write_text(
        "import io\nimport urllib.request\n"
        "def fake_open(self, request, timeout=None):\n"
        f"    return io.BytesIO({body.encode()!r})\n"
        "urllib.request.OpenerDirector.open = fake_open\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(fake_site))
    clone, baseline, candidate = (tmp_path / name for name in ("clone", "baseline", "candidate"))
    subprocess.run(
        ("git", "clone", "-q", "--local", "--no-hardlinks", "--no-checkout", str(root), str(clone)),
        check=True,
    )
    baseline_commit = validation_gate._git(root, "rev-parse", "c46c27a").decode().strip()
    head = validation_gate._git(root, "rev-parse", "HEAD").decode().strip()
    for path, commit in ((baseline, baseline_commit), (candidate, head)):
        subprocess.run(
            ("git", "-C", str(clone), "worktree", "add", "-q", "--detach", str(path), commit),
            check=True,
        )
    shutil.copytree(root / gate.HARNESS, candidate / gate.HARNESS,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    def commit(message: str) -> None:
        subprocess.run(("git", "-C", str(candidate), "add", "."), check=True)
        subprocess.run(
            ("git", "-C", str(candidate), "-c", "user.name=Test",
             "-c", "user.email=test@example.invalid", "commit", "-qm", message),
            check=True,
        )

    commit("PF harness")
    model = Path("/Users/khe/.cache/maeumcall-models/kanana-1.5-2.1b-q5-k-m.gguf")
    if not model.is_file():
        pytest.skip("frozen Q5 model file unavailable for protocol integrity check")
    validation = candidate / "evals/structured_nlu/data/ai_heldout/nlu-internal-validation-pair-protocol.v1.json"
    pf_protocol = candidate / "evals/structured_nlu/data/ai_heldout/pf-synthetic-protocol.json"
    output = tmp_path / "pf-result.json"
    journal = tmp_path / "pf-journal.jsonl"
    private = tmp_path / "pf-raw"
    receipt = tmp_path / "pf-verified.json"
    pf_protocol.write_text(json.dumps(gate.build(
        root=candidate, baseline_root=baseline, validation_protocol=validation,
        model_path=model, result=output, journal=journal,
        private_dir=private, receipt=receipt,
    ), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    commit("PF protocol")
    assert gate.check(
        protocol_path=pf_protocol, root=candidate, baseline_root=baseline,
        validation_protocol=validation, model_path=model,
    )[0]["kind"] == gate.KIND

    state = {"restarts": 0}

    def observed(*_args, **_kwargs):
        return {
            "Id": "d" * 64,
            "State": {"StartedAt": f"start-{state['restarts']}", "Running": True, "OOMKilled": False},
            "RestartCount": state["restarts"],
        }

    def boundary(stream, _name, _model, _protocol, phase, count):
        row = {
            "event": "server_boundary", "phase": phase, "completed_cases": count,
            "running": True, "oom_killed": False, "exit_code": 0,
            "restart_count": state["restarts"], "container_id": "d" * 64,
            "started_at": f"start-{state['restarts']}",
            "docker_host_memory_bytes": validation_gate.LOCAL_RUNTIME["docker_host_min_memory_bytes"],
            "memory_usage": "1GiB / 10GiB", "healthy": True,
        }
        pf_run.server._append(stream, row)
        return row

    original_run = subprocess.run

    def intercept(command, *args, **kwargs):
        if tuple(command[:2]) == ("docker", "restart"):
            state["restarts"] += 1
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(pf_run.server, "verify_container", observed)
    monkeypatch.setattr(pf_run, "_boundary", boundary)
    monkeypatch.setattr(pf_run.subprocess, "run", intercept)
    common = dict(
        root=candidate, baseline_root=baseline, validation_protocol=validation,
        protocol_path=pf_protocol, model_path=model,
    )
    unverified = pf_run.run(**common, container_name="fake")
    assert unverified["verification_status"] == "unverified"
    assert len(unverified["projections"]["baseline"]) == 16
    assert len(unverified["projections"]["candidate"]) == 16
    assert state["restarts"] == 3
    verified = pf_verify.verify(**common)
    assert verified["verification_status"] == "verified"
    assert verified["gate_passed"] is True
    assert verified["summary"]["new_direct_danger_misses"] == []
    assert verified["arm_evaluations"] == 32
    receipt.unlink()
    next(private.iterdir()).write_text("altered", encoding="utf-8")
    with pytest.raises(ValueError, match="PF worker failed"):
        pf_verify.verify(**common)
