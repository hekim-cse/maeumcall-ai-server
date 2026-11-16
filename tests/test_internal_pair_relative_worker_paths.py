"""Child workers must see the same paths regardless of their worktree cwd."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from experiments.internal_test_pair_v1 import run as test_run
from experiments.internal_test_pair_v1 import verify as test_verify
from experiments.internal_validation_pair_v1 import run as validation_run
from experiments.internal_validation_pf_sentinel_v1 import run as pf_run


@pytest.fixture
def relative_roots(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate"
    baseline = tmp_path / "baseline"
    candidate.mkdir()
    baseline.mkdir()
    monkeypatch.chdir(candidate)
    return candidate, baseline


@pytest.mark.parametrize(
    ("module", "worker_path"),
    [
        (test_run, "experiments/internal_test_pair_v1/worker.py"),
        (validation_run, "experiments/internal_validation_pair_v1/worker.py"),
    ],
)
def test_baseline_worker_uses_absolute_candidate_paths(
    module, worker_path, relative_roots, monkeypatch
):
    candidate, baseline = relative_roots
    observed = {}

    def fake_run(command, **kwargs):
        observed.update(command=command, **kwargs)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"status":"complete","arm":"baseline","case_id":"C01"}',
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    arguments = {
        "protocol": {
            "request_policy": {},
            "arms": {"baseline": {"commit": "a", "source_manifest": {}}},
        },
        "candidate_root": Path("."),
        "arm_roots": {"baseline": Path("../baseline")},
        "private_dir": Path("../private"),
        "arm": "baseline",
        "case_id": "C01",
        "worktree_head": "head",
    }
    if module is test_run:
        arguments["protocol"].update(input_commit="input", inputs={"test_dataset": "hash"})
        arguments.update(dataset_key="test_dataset", dataset_relative=Path("dataset.json"))
    module._worker(**arguments)
    command = observed["command"]
    assert command[1] == str(candidate / worker_path)
    assert command[command.index("--arm-root") + 1] == str(baseline)
    assert command[command.index("--private-dir") + 1] == str(candidate.parent / "private")
    assert observed["cwd"] == baseline
    if module is test_run:
        assert json.loads(observed["input"])["data_root"] == str(candidate)


def test_test_replay_uses_absolute_candidate_paths(relative_roots, monkeypatch):
    candidate, baseline = relative_roots
    observed = {}

    def fake_run(command, **kwargs):
        observed.update(command=command, **kwargs)
        return subprocess.CompletedProcess(command, 1, stdout="")

    monkeypatch.setattr(test_verify.subprocess, "run", fake_run)
    with pytest.raises(ValueError, match="raw replay failed"):
        test_verify._replay(
            candidate_root=Path("."),
            arm_root=Path("../baseline"),
            arm="baseline",
            case_id="C01",
            private_dir=Path("../private"),
            protocol={
                "request_policy": {},
                "arms": {"baseline": {"commit": "a", "source_manifest": {}}},
                "input_commit": "input",
                "inputs": {"test_dataset": "hash"},
            },
            attempts=[],
            worktree_head="head",
            dataset_key="test_dataset",
            dataset_relative=Path("dataset.json"),
        )
    command = observed["command"]
    assert command[1] == str(candidate / "experiments/internal_test_pair_v1/worker.py")
    assert command[command.index("--arm-root") + 1] == str(baseline)
    assert observed["cwd"] == baseline
    assert json.loads(observed["input"])["data_root"] == str(candidate)


def test_pf_baseline_worker_uses_absolute_candidate_paths(relative_roots, monkeypatch):
    candidate, baseline = relative_roots
    observed = {}

    def fake_run(command, **kwargs):
        observed.update(command=command, **kwargs)
        return subprocess.CompletedProcess(command, 0, stdout='{"arm":"baseline","case_id":"PF01"}')

    monkeypatch.setattr(pf_run.subprocess, "run", fake_run)
    pf_run._worker(
        Path("."),
        Path("../baseline"),
        {
            "arm": "baseline",
            "case_id": "PF01",
            "arm_root": "../baseline",
            "private_dir": "../private",
        },
    )
    command = observed["command"]
    assert command[1] == str(candidate / "experiments/internal_validation_pf_sentinel_v1/worker.py")
    assert observed["cwd"] == baseline
    payload = json.loads(observed["input"])
    assert payload["arm_root"] == str(baseline)
    assert payload["private_dir"] == str(candidate.parent / "private")
