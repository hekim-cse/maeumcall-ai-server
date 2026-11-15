"""Exercise the whole 32-pair journal and receipt path without a model or Docker."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from evals.structured_nlu.ai_heldout import AIHeldoutDataset
from evals.structured_nlu.schema import CasePrediction, EvaluationAttempt
from experiments.internal_validation_pair_v1 import qualification as gate
from experiments.internal_validation_pair_v1 import run as pair_run
from experiments.internal_validation_pair_v1 import verify as pair_verify


def test_full_model_free_roundtrip_and_raw_tamper(monkeypatch, tmp_path):
    dataset = AIHeldoutDataset.model_validate_json(
        (gate.ROOT / gate.INPUT_PATHS["validation_dataset"]).read_bytes()
    )
    ids = [case.id for case in dataset.cases]
    protocol = {
        "case_order": ids,
        "pair_order": gate.pair_order(ids),
        "request_policy": gate.REQUEST_POLICY,
        "local_runtime": gate.LOCAL_RUNTIME,
        "arms": {
            "baseline": {"commit": "a" * 40, "source_manifest": {}},
            "candidate": {"commit": "b" * 40, "source_manifest": {}},
        },
    }
    monkeypatch.setattr(gate, "preflight", lambda **kwargs: (protocol, "c" * 64))
    monkeypatch.setattr(
        gate,
        "_git",
        lambda root, *args: ("a" * 40 if root.name == "baseline" else "b" * 40).encode(),
    )
    state = {"starts": 0}
    container = {
        "Id": "d" * 64,
        "State": {"StartedAt": "start-0", "Running": True, "OOMKilled": False},
        "RestartCount": 0,
    }

    def observe(*args, **kwargs):
        container["State"]["StartedAt"] = f"start-{state['starts']}"
        container["RestartCount"] = state["starts"]
        return container.copy()

    def boundary(stream, _name, _model, _protocol, phase, count):
        row = {
            "event": "server_boundary",
            "phase": phase,
            "completed_cases": count,
            "running": True,
            "oom_killed": False,
            "exit_code": 0,
            "restart_count": state["starts"],
            "container_id": "d" * 64,
            "started_at": f"start-{state['starts']}",
            "docker_host_memory_bytes": gate.LOCAL_RUNTIME["docker_host_min_memory_bytes"],
            "memory_usage": "1GiB / 10GiB",
            "healthy": True,
        }
        pair_run._append(stream, row)
        return row

    def restart(*args, **kwargs):
        state["starts"] += 1

    def fake_worker(*, private_dir, arm, case_id, **kwargs):
        raw = b"{}"
        path = private_dir / f"{arm}-{case_id}-attempt1.txt"
        path.write_bytes(raw)
        os.chmod(path, 0o600)
        prediction = CasePrediction(
            case_id=case_id,
            attempts=(
                EvaluationAttempt(
                    contract_valid=False, latency_ms=1, error_type="StructuredKeyError"
                ),
            ),
        )
        return {
            "status": "complete",
            "case_id": case_id,
            "arm": arm,
            "prediction": prediction.model_dump(mode="json"),
            "raw_attempts": [
                {
                    "attempt": 1,
                    "status": "received",
                    "raw_sha256": hashlib.sha256(raw).hexdigest(),
                    "raw_bytes": len(raw),
                    "error_type": None,
                }
            ],
        }

    monkeypatch.setattr(pair_run.server, "verify_container", observe)
    monkeypatch.setattr(pair_run, "_boundary", boundary)
    monkeypatch.setattr(pair_run.subprocess, "run", restart)
    monkeypatch.setattr(pair_run, "_worker", fake_worker)
    monkeypatch.setattr(
        pair_verify,
        "_replay",
        lambda *, case_id, **kwargs: CasePrediction(
            case_id=case_id,
            attempts=(
                EvaluationAttempt(
                    contract_valid=False, latency_ms=9, error_type="StructuredKeyError"
                ),
            ),
        ),
    )

    baseline = tmp_path / "baseline"
    baseline.mkdir()
    output = tmp_path / "result.json"
    journal = tmp_path / "journal.jsonl"
    private = tmp_path / "private"
    receipt = tmp_path / "verified.json"
    common = dict(
        protocol_path=Path("unused"),
        baseline_root=baseline,
        candidate_root=gate.ROOT,
        model_path=Path("unused"),
        output=output,
        journal=journal,
        private_dir=private,
        receipt=receipt,
    )
    result = pair_run.run(**common, container_name="fake")
    assert state["starts"] == 7
    assert result["verification_status"] == "unverified"
    assert "summaries" not in result and "paired_counts" not in result
    assert not receipt.exists()
    verified = pair_verify.verify(**common)
    assert verified["verification_status"] == "verified"
    assert verified["paired_counts"]["both_incorrect"] == 32
    assert json.loads(receipt.read_text()) == verified
    receipt.unlink()
    next(private.iterdir()).write_text("tampered")
    with pytest.raises(ValueError, match="private raw response"):
        pair_verify.verify(**common)


def test_real_git_protocol_and_raw_replay_with_fake_q5(monkeypatch, tmp_path):
    """Keep Git preflight and arm raw replay real; replace only Docker and Q5 transport."""
    fake_site = tmp_path / "fake_site"
    fake_site.mkdir()
    (fake_site / "sitecustomize.py").write_text(
        "import io\nimport urllib.request\n"
        "def fake_open(self, request, timeout=None):\n"
        '    return io.BytesIO(b\'{"choices":[{"message":{"content":"{}"}}]}\')\n'
        "urllib.request.OpenerDirector.open = fake_open\n"
    )
    monkeypatch.setenv("PYTHONPATH", str(fake_site))
    clone = tmp_path / "clone"
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    subprocess.run(
        (
            "git",
            "clone",
            "-q",
            "--local",
            "--no-hardlinks",
            "--no-checkout",
            str(gate.ROOT),
            str(clone),
        ),
        check=True,
    )
    subprocess.run(
        (
            "git",
            "-C",
            str(clone),
            "worktree",
            "add",
            "-q",
            "--detach",
            str(baseline),
            "c46c27a",
        ),
        check=True,
    )
    subprocess.run(
        (
            "git",
            "-C",
            str(clone),
            "worktree",
            "add",
            "-q",
            "--detach",
            str(candidate),
            "04af278",
        ),
        check=True,
    )
    shutil.copytree(
        gate.ROOT / gate.HARNESS_ROOT,
        candidate / gate.HARNESS_ROOT,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    def commit(message):
        subprocess.run(("git", "-C", str(candidate), "add", "."), check=True)
        subprocess.run(
            (
                "git",
                "-C",
                str(candidate),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qm",
                message,
            ),
            check=True,
        )

    commit("harness")
    model = tmp_path / "fake.gguf"
    model.write_bytes(b"synthetic Q5 boundary")
    monkeypatch.setattr(gate, "MODEL_SHA256", gate._file_sha(model))
    request = {
        **gate.REQUEST_POLICY,
        "endpoint": "http://127.0.0.1:18081/v1/chat/completions",
    }
    monkeypatch.setattr(gate, "REQUEST_POLICY", request)
    output = tmp_path / "result.json"
    journal = tmp_path / "journal.jsonl"
    private = tmp_path / "private"
    receipt = tmp_path / "verified.json"
    protocol_path = candidate / "protocol.json"
    frozen = gate.build_protocol(
        baseline_root=baseline,
        baseline_commit=gate._git(baseline, "rev-parse", "HEAD").decode().strip(),
        candidate_root=candidate,
        candidate_commit="04af27849563f7b30845441e0f8fc6ca90f876ff",
        model_path=model,
        output=output,
        journal=journal,
        private_dir=private,
        receipt=receipt,
    )
    protocol_path.write_text(json.dumps(frozen, ensure_ascii=False))
    commit("protocol")
    common = dict(
        protocol_path=protocol_path,
        baseline_root=baseline,
        candidate_root=candidate,
        model_path=model,
        output=output,
        journal=journal,
        private_dir=private,
        receipt=receipt,
    )
    assert gate.preflight(**common)[0] == frozen

    state = {"restarts": 0}

    def observed(*args, **kwargs):
        return {
            "Id": "d" * 64,
            "State": {
                "StartedAt": f"start-{state['restarts']}",
                "Running": True,
                "OOMKilled": False,
            },
            "RestartCount": state["restarts"],
        }

    def boundary(stream, _name, _model, _protocol, phase, count):
        row = {
            "event": "server_boundary",
            "phase": phase,
            "completed_cases": count,
            "running": True,
            "oom_killed": False,
            "exit_code": 0,
            "restart_count": state["restarts"],
            "container_id": "d" * 64,
            "started_at": f"start-{state['restarts']}",
            "docker_host_memory_bytes": gate.LOCAL_RUNTIME["docker_host_min_memory_bytes"],
            "memory_usage": "1GiB / 10GiB",
            "healthy": True,
        }
        pair_run._append(stream, row)
        return row

    original_run = subprocess.run

    def intercept(command, *args, **kwargs):
        if tuple(command[:2]) == ("docker", "restart"):
            state["restarts"] += 1
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(pair_run.server, "verify_container", observed)
    monkeypatch.setattr(pair_run, "_boundary", boundary)
    monkeypatch.setattr(pair_run.subprocess, "run", intercept)
    result = pair_run.run(**common, container_name="fake")
    assert result["verification_status"] == "unverified"
    assert len(result["predictions"]["baseline"]) == 32
    assert len(result["predictions"]["candidate"]) == 32
    assert state["restarts"] == 7
    verified = pair_verify.verify(**common)
    assert verified["verification_status"] == "verified"
    assert verified["paired_counts"]["both_incorrect"] == 32
