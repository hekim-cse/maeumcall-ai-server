"""Private raw and restart evidence must fail closed before paired scoring."""

from __future__ import annotations

import hashlib
import os

import pytest

from experiments.internal_validation_pair_v1 import qualification as gate
from experiments.internal_validation_pair_v1 import verify, worker


def _boundary(*, phase: str, count: int, started: str, restarts: int) -> dict:
    return {
        "event": "server_boundary",
        "phase": phase,
        "completed_cases": count,
        "running": True,
        "oom_killed": False,
        "exit_code": 0,
        "restart_count": restarts,
        "container_id": "a" * 64,
        "started_at": started,
        "docker_host_memory_bytes": gate.LOCAL_RUNTIME["docker_host_min_memory_bytes"],
        "memory_usage": "1GiB / 10GiB",
        "healthy": True,
    }


def test_restart_boundary_rejects_unchanged_start_time():
    before = _boundary(phase="before_restart", count=8, started="time-a", restarts=0)
    after = _boundary(phase="after_restart", count=8, started="time-a", restarts=1)
    with pytest.raises(ValueError, match="planned restart"):
        verify._boundary(after, phase="after_restart", completed=8, previous=before)


def test_restart_boundary_rejects_oom():
    row = _boundary(phase="initial", count=0, started="time-a", restarts=0)
    row["oom_killed"] = True
    with pytest.raises(ValueError, match="OOM"):
        verify._boundary(row, phase="initial", completed=0, previous=None)


def test_raw_replay_metadata_rejects_tampered_bytes(tmp_path):
    path = tmp_path / "baseline-iv01-attempt1.txt"
    path.write_text('{"answer":"first"}')
    os.chmod(path, 0o600)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    item = {
        "attempt": 1,
        "status": "received",
        "raw_sha256": digest,
        "raw_bytes": path.stat().st_size,
        "error_type": None,
    }
    assert verify._raw([item], tmp_path, "baseline", "iv01") == {path.name}
    path.write_text('{"answer":"second"}')
    with pytest.raises(ValueError, match="private raw response"):
        verify._raw([item], tmp_path, "baseline", "iv01")


def test_pair_paths_reject_inside_either_worktree(tmp_path):
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    baseline.mkdir()
    candidate.mkdir()
    with pytest.raises(ValueError, match="outside both"):
        gate._output_paths(
            candidate / "result.json",
            tmp_path / "journal.jsonl",
            tmp_path / "raw",
            tmp_path / "receipt.json",
            baseline,
            candidate,
        )


def test_offline_replay_reproduces_live_analyzer_without_model(monkeypatch, tmp_path):
    from evals.structured_nlu.ai_heldout import AIHeldoutDataset
    from evals.structured_nlu.schema import CasePrediction
    from scripts import run_ai_heldout_pair

    monkeypatch.setattr(worker, "_check_arm", lambda *args, **kwargs: None)
    monkeypatch.setattr(run_ai_heldout_pair, "_post_completion", lambda *args: "{}")
    raw_dir = tmp_path / "private"
    raw_dir.mkdir(mode=0o700)
    dataset = AIHeldoutDataset.model_validate_json(
        (gate.ROOT / gate.INPUT_PATHS["validation_dataset"]).read_bytes()
    )
    params = {
        "arm_root": gate.ROOT,
        "arm": "baseline",
        "case_id": dataset.cases[0].id,
        "private_dir": raw_dir,
        "request": gate.REQUEST_POLICY,
        "commit": "0" * 40,
        "manifest": {},
        "expected_head": "0" * 40,
    }
    live = worker.one_case(mode="live", **params)
    assert live["status"] == "complete"
    assert len(live["raw_attempts"]) == 2
    replay = worker.one_case(mode="replay", recorded_attempts=live["raw_attempts"], **params)
    assert replay["status"] == "complete"
    assert verify._semantic_prediction(CasePrediction.model_validate(live["prediction"])) == (
        verify._semantic_prediction(CasePrediction.model_validate(replay["prediction"]))
    )
    (raw_dir / f"baseline-{params['case_id']}-attempt1.txt").write_text("changed")
    with pytest.raises(RuntimeError, match="replay private raw digest"):
        worker.one_case(mode="replay", recorded_attempts=live["raw_attempts"], **params)
