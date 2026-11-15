"""The exposed development baseline must not be mistaken for a fresh test."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals.structured_nlu.schema import CasePrediction, EvaluationAttempt
from experiments.nlu_current_baseline_v1 import run as runner


def _fake_server(monkeypatch) -> None:
    generation = 0

    def verified(*_args):
        return {"Id": "a" * 64, "State": {"StartedAt": str(generation)}}

    monkeypatch.setattr(runner, "verify_container", verified)

    def boundary(stream, _name, _model, _protocol, *, phase, completed_cases):
        nonlocal generation
        if phase == "after_restart":
            generation += 1
        row = {"event": "server_boundary", "phase": phase, "completed_cases": completed_cases}
        runner._append(stream, row)
        return {**row, "container_id": "a" * 64, "started_at": str(generation)}

    monkeypatch.setattr(
        runner,
        "_server_boundary",
        boundary,
    )
    monkeypatch.setattr(runner.subprocess, "run", lambda *_args, **_kwargs: None)


def _failed_prediction(case, *, endpoint, model_id, policy, completion_post):
    completion_post(endpoint, model_id, [], policy)
    return CasePrediction(
        case_id=case.id,
        attempts=(EvaluationAttempt(contract_valid=False, latency_ms=1, error_type="ValueError"),),
    )


def test_reviewed_input_is_exposed_balanced_development() -> None:
    reviewed = runner._reviewed()
    assert len(reviewed.dataset.cases) == 32
    assert set(reviewed.scenario_counts.values()) == {2}
    assert [case.id for case in reviewed.dataset.cases] == [
        f"ai-heldout-ah{i:02}" for i in range(1, 33)
    ]
    assert runner.SCOPE.endswith("development_only")
    assert runner.RUNTIME["memory_bytes"] == 10 * 1024**3
    assert runner.RUNTIME["docker_desktop_target_memory_bytes"] == 12 * 1024**3
    assert runner.RUNTIME["docker_host_min_memory_bytes"] == 23 * 1024**3 // 2
    assert runner.RUNTIME["restart_interval_cases"] == 8


def test_protocol_binds_current_sources_and_reviewed_inputs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runner, "_file_sha", lambda _path: runner.MODEL_SHA)

    def committed(*args):
        assert args[0] == "show"
        relative = args[1].split(":", 1)[1]
        return (runner.ROOT / relative).read_bytes()

    monkeypatch.setattr(runner, "_git", committed)
    protocol = runner.build_protocol("a" * 40, tmp_path / "model.gguf")
    assert protocol["scope"] == runner.SCOPE
    assert protocol["case_order"] == [f"ai-heldout-ah{i:02}" for i in range(1, 33)]
    assert protocol["input_hashes"]["dataset"] == runner._sha(runner.INPUTS["dataset"].read_bytes())
    assert "experiments/nlu_current_baseline_v1/verify.py" in protocol["source_manifest"]
    assert "services/flow/service_workflow/structured.py" in protocol["source_manifest"]


def test_existing_result_blocks_model_calls(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    output.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(
        runner,
        "load_protocol",
        lambda *_args: pytest.fail("must reject before loading protocol"),
    )
    with pytest.raises(FileExistsError):
        runner.run(
            protocol_path=tmp_path / "protocol.json",
            model_path=tmp_path / "model.gguf",
            output=output,
            journal=tmp_path / "journal.jsonl",
            private_dir=tmp_path / "raw",
            container_name="local-test",
        )


def test_existing_private_raw_blocks_model_calls(monkeypatch, tmp_path: Path) -> None:
    private_dir = tmp_path / "raw"
    private_dir.mkdir()
    monkeypatch.setattr(
        runner,
        "load_protocol",
        lambda *_args: pytest.fail("must reject before loading protocol"),
    )
    with pytest.raises(FileExistsError):
        runner.run(
            protocol_path=tmp_path / "protocol.json",
            model_path=tmp_path / "model.gguf",
            output=tmp_path / "result.json",
            journal=tmp_path / "journal.jsonl",
            private_dir=private_dir,
            container_name="local-test",
        )


def test_result_contains_only_normalized_predictions(monkeypatch, tmp_path: Path) -> None:
    reviewed = runner._reviewed()
    protocol = {
        "request_policy": runner.REQUEST,
        "local_runtime": runner.RUNTIME,
        "case_order": [case.id for case in reviewed.dataset.cases],
    }
    monkeypatch.setattr(runner, "load_protocol", lambda *_args: (protocol, "f" * 64))
    _fake_server(monkeypatch)
    monkeypatch.setattr(runner, "_post_completion", lambda *_args: "{}")
    calls = []

    def fake_case(case, *, endpoint, model_id, policy, completion_post):
        calls.append((case.id, endpoint, model_id, policy.max_tokens))
        completion_post(endpoint, model_id, [], policy)
        return CasePrediction(
            case_id=case.id,
            attempts=(
                EvaluationAttempt(contract_valid=False, latency_ms=1, error_type="ValueError"),
            ),
        )

    monkeypatch.setattr(runner, "_run_case", fake_case)
    output = tmp_path / "result.json"
    journal = tmp_path / "journal.jsonl"
    private_dir = tmp_path / "raw"
    result = runner.run(
        protocol_path=tmp_path / "protocol.json",
        model_path=tmp_path / "model.gguf",
        output=output,
        journal=journal,
        private_dir=private_dir,
        container_name="local-test",
    )
    assert len(calls) == 32
    assert result["summary"]["counts"]["fully_correct_cases"] == 0
    assert result["protocol_sha256"] == "f" * 64
    saved = output.read_text(encoding="utf-8")
    assert json.loads(saved) == result
    assert "user_message" not in saved
    assert "prompt" not in saved
    assert "raw" not in saved
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 74
    assert rows[0] == {"event": "header", "protocol_sha256": "f" * 64}
    assert rows[1] == {"event": "server_boundary", "phase": "initial", "completed_cases": 0}
    assert rows[-1] == {"event": "summary", "summary": result["summary"]}
    assert result["journal_sha256"] == runner._file_sha(journal)
    assert rows[3]["raw_attempts"] == [
        {
            "attempt": 1,
            "status": "received",
            "raw_sha256": runner._sha(b"{}"),
            "raw_bytes": 2,
            "error_type": None,
        }
    ]
    assert (private_dir / "ai-heldout-ah01-attempt1.txt").read_text() == "{}"
    assert private_dir.stat().st_mode & 0o777 == 0o700
    assert (private_dir / "ai-heldout-ah01-attempt1.txt").stat().st_mode & 0o777 == 0o600


def test_interrupted_journal_blocks_reexecution(monkeypatch, tmp_path: Path) -> None:
    reviewed = runner._reviewed()
    protocol = {
        "request_policy": runner.REQUEST,
        "local_runtime": runner.RUNTIME,
        "case_order": [case.id for case in reviewed.dataset.cases],
    }
    monkeypatch.setattr(runner, "load_protocol", lambda *_args: (protocol, "f" * 64))
    _fake_server(monkeypatch)
    calls = 0

    def interrupted(_case, **_kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("interrupted")

    monkeypatch.setattr(runner, "_run_case", interrupted)
    output = tmp_path / "result.json"
    journal = tmp_path / "journal.jsonl"
    private_dir = tmp_path / "raw"
    with pytest.raises(RuntimeError, match="interrupted"):
        runner.run(
            protocol_path=tmp_path / "protocol.json",
            model_path=tmp_path / "model.gguf",
            output=output,
            journal=journal,
            private_dir=private_dir,
            container_name="local-test",
        )
    assert calls == 1
    assert not output.exists()
    assert private_dir.is_dir()
    assert [json.loads(line)["event"] for line in journal.read_text().splitlines()] == [
        "header",
        "server_boundary",
        "begin",
    ]
    with pytest.raises(FileExistsError):
        runner.run(
            protocol_path=tmp_path / "protocol.json",
            model_path=tmp_path / "model.gguf",
            output=output,
            journal=journal,
            private_dir=private_dir,
            container_name="local-test",
        )
    assert calls == 1


def test_transport_failure_has_bounded_status_without_raw_file(monkeypatch, tmp_path: Path) -> None:
    reviewed = runner._reviewed()
    protocol = {
        "request_policy": runner.REQUEST,
        "local_runtime": runner.RUNTIME,
        "case_order": [case.id for case in reviewed.dataset.cases],
    }
    monkeypatch.setattr(runner, "load_protocol", lambda *_args: (protocol, "f" * 64))
    _fake_server(monkeypatch)
    monkeypatch.setattr(
        runner, "_post_completion", lambda *_args: (_ for _ in ()).throw(OSError("secret"))
    )

    calls = 0

    def fake_case(case, *, endpoint, model_id, policy, completion_post):
        nonlocal calls
        calls += 1
        completion_post(endpoint, model_id, [], policy)
        pytest.fail("completion failure must escape before prediction")

    monkeypatch.setattr(runner, "_run_case", fake_case)
    output = tmp_path / "result.json"
    journal = tmp_path / "journal.jsonl"
    private_dir = tmp_path / "raw"
    with pytest.raises(runner.CompletionFailure, match="model completion failed: OSError"):
        runner.run(
            protocol_path=tmp_path / "protocol.json",
            model_path=tmp_path / "model.gguf",
            output=output,
            journal=journal,
            private_dir=private_dir,
            container_name="local-test",
        )
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert calls == 1
    assert not output.exists()
    assert [row["event"] for row in rows] == ["header", "server_boundary", "begin", "end"]
    assert rows[3]["status"] == "completion_error"
    assert rows[3]["raw_attempts"] == [
        {
            "attempt": 1,
            "status": "transport_error",
            "raw_sha256": None,
            "raw_bytes": None,
            "error_type": "OSError",
        }
    ]
    assert list(private_dir.iterdir()) == []
    assert "secret" not in journal.read_text()


def test_live_analyzer_does_not_retry_transport_failure(monkeypatch, tmp_path: Path) -> None:
    reviewed = runner._reviewed()
    protocol = {
        "request_policy": runner.REQUEST,
        "local_runtime": runner.RUNTIME,
        "case_order": [case.id for case in reviewed.dataset.cases],
    }
    monkeypatch.setattr(runner, "load_protocol", lambda *_args: (protocol, "f" * 64))
    _fake_server(monkeypatch)
    calls = 0

    def disconnect(*_args):
        nonlocal calls
        calls += 1
        raise ConnectionResetError("response content must not leak")

    monkeypatch.setattr(runner, "_post_completion", disconnect)
    output = tmp_path / "result.json"
    journal = tmp_path / "journal.jsonl"
    with pytest.raises(runner.CompletionFailure, match="ConnectionResetError"):
        runner.run(
            protocol_path=tmp_path / "protocol.json",
            model_path=tmp_path / "model.gguf",
            output=output,
            journal=journal,
            private_dir=tmp_path / "raw",
            container_name="local-test",
        )
    assert calls == 1
    assert not output.exists()
    assert "response content" not in journal.read_text()


def test_final_server_failure_prevents_summary_and_result(monkeypatch, tmp_path: Path) -> None:
    reviewed = runner._reviewed()
    protocol = {
        "request_policy": runner.REQUEST,
        "local_runtime": runner.RUNTIME,
        "case_order": [case.id for case in reviewed.dataset.cases],
    }
    monkeypatch.setattr(runner, "load_protocol", lambda *_args: (protocol, "f" * 64))
    _fake_server(monkeypatch)
    original_boundary = runner._server_boundary

    def boundary(stream, name, model, selected_protocol, *, phase, completed_cases):
        recorded = original_boundary(
            stream, name, model, selected_protocol, phase=phase, completed_cases=completed_cases
        )
        if phase == "final":
            raise ValueError("model server health failed at boundary")
        return recorded

    monkeypatch.setattr(runner, "_server_boundary", boundary)
    monkeypatch.setattr(runner, "_post_completion", lambda *_args: "{}")

    def fake_case(case, *, endpoint, model_id, policy, completion_post):
        completion_post(endpoint, model_id, [], policy)
        return CasePrediction(
            case_id=case.id,
            attempts=(
                EvaluationAttempt(contract_valid=False, latency_ms=1, error_type="ValueError"),
            ),
        )

    monkeypatch.setattr(runner, "_run_case", fake_case)
    output = tmp_path / "result.json"
    journal = tmp_path / "journal.jsonl"
    with pytest.raises(ValueError, match="health failed"):
        runner.run(
            protocol_path=tmp_path / "protocol.json",
            model_path=tmp_path / "model.gguf",
            output=output,
            journal=journal,
            private_dir=tmp_path / "raw",
            container_name="local-test",
        )
    assert not output.exists()
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert rows[-1] == {"event": "server_boundary", "phase": "final", "completed_cases": 32}
    assert [row["phase"] for row in rows if row["event"] == "server_boundary"] == [
        "initial",
        "before_restart",
        "after_restart",
        "before_restart",
        "after_restart",
        "before_restart",
        "after_restart",
        "final",
    ]
    assert not any(row["event"] == "summary" for row in rows)


def test_oom_boundary_records_failure_before_stopping(monkeypatch, tmp_path: Path) -> None:
    observed = {
        "Id": "a" * 64,
        "State": {
            "Running": False,
            "OOMKilled": True,
            "ExitCode": 137,
            "StartedAt": "2026-11-16T00:00:00Z",
        },
        "RestartCount": 1,
    }
    monkeypatch.setattr(runner, "_inspect_container", lambda _name: observed)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=str(12 * 1024**3)),
    )
    monkeypatch.setattr(
        runner,
        "verify_container",
        lambda *_args: pytest.fail("stopped container must not be verified as healthy"),
    )
    journal = tmp_path / "journal.jsonl"
    with journal.open("x", encoding="utf-8") as stream:
        with pytest.raises(ValueError, match="health failed"):
            runner._server_boundary(
                stream,
                "local-test",
                tmp_path / "model.gguf",
                {"request_policy": runner.REQUEST, "local_runtime": runner.RUNTIME},
                phase="final",
                completed_cases=32,
            )
    assert json.loads(journal.read_text()) == {
        "event": "server_boundary",
        "phase": "final",
        "completed_cases": 32,
        "running": False,
        "oom_killed": True,
        "exit_code": 137,
        "restart_count": 1,
        "container_id": "a" * 64,
        "started_at": "2026-11-16T00:00:00Z",
        "docker_host_memory_bytes": 12 * 1024**3,
        "memory_usage": None,
        "healthy": False,
    }


def test_initial_container_change_prevents_first_model_call(monkeypatch, tmp_path: Path) -> None:
    protocol = {
        "request_policy": runner.REQUEST,
        "local_runtime": runner.RUNTIME,
        "case_order": [case.id for case in runner._reviewed().dataset.cases],
    }
    monkeypatch.setattr(runner, "load_protocol", lambda *_args: (protocol, "f" * 64))
    _fake_server(monkeypatch)
    original_boundary = runner._server_boundary

    def changed_boundary(stream, name, model, selected_protocol, *, phase, completed_cases):
        row = original_boundary(
            stream, name, model, selected_protocol, phase=phase, completed_cases=completed_cases
        )
        return {**row, "started_at": "unexpected"}

    monkeypatch.setattr(runner, "_server_boundary", changed_boundary)
    monkeypatch.setattr(runner, "_run_case", lambda *_args, **_kwargs: pytest.fail("no call"))
    output = tmp_path / "result.json"
    journal = tmp_path / "journal.jsonl"
    with pytest.raises(ValueError, match="changed before initial boundary"):
        runner.run(
            protocol_path=tmp_path / "protocol.json",
            model_path=tmp_path / "model.gguf",
            output=output,
            journal=journal,
            private_dir=tmp_path / "raw",
            container_name="local-test",
        )
    assert not output.exists()
    assert [json.loads(line)["event"] for line in journal.read_text().splitlines()] == [
        "header",
        "server_boundary",
    ]


@pytest.mark.parametrize(
    ("changed_phase", "changed_after_cases"),
    [("before_restart", 16), ("final", 32)],
)
def test_unplanned_restart_prevents_result(
    monkeypatch, tmp_path: Path, changed_phase: str, changed_after_cases: int
) -> None:
    protocol = {
        "request_policy": runner.REQUEST,
        "local_runtime": runner.RUNTIME,
        "case_order": [case.id for case in runner._reviewed().dataset.cases],
    }
    monkeypatch.setattr(runner, "load_protocol", lambda *_args: (protocol, "f" * 64))
    _fake_server(monkeypatch)
    original_boundary = runner._server_boundary

    def changed_boundary(stream, name, model, selected_protocol, *, phase, completed_cases):
        row = original_boundary(
            stream, name, model, selected_protocol, phase=phase, completed_cases=completed_cases
        )
        if phase == changed_phase and completed_cases == changed_after_cases:
            return {**row, "started_at": "unexpected"}
        return row

    monkeypatch.setattr(runner, "_server_boundary", changed_boundary)
    monkeypatch.setattr(runner, "_post_completion", lambda *_args: "{}")
    monkeypatch.setattr(runner, "_run_case", _failed_prediction)
    output = tmp_path / "result.json"
    journal = tmp_path / "journal.jsonl"
    with pytest.raises(ValueError, match="restarted outside planned boundary"):
        runner.run(
            protocol_path=tmp_path / "protocol.json",
            model_path=tmp_path / "model.gguf",
            output=output,
            journal=journal,
            private_dir=tmp_path / "raw",
            container_name="local-test",
        )
    assert not output.exists()
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert sum(row["event"] == "end" for row in rows) == changed_after_cases
    assert rows[-1]["event"] == "server_boundary"
    assert not any(row["event"] == "summary" for row in rows)


def test_boundary_rejects_container_change_between_inspections(monkeypatch, tmp_path: Path) -> None:
    observed = {
        "Id": "a" * 64,
        "State": {
            "Running": True,
            "OOMKilled": False,
            "ExitCode": 0,
            "StartedAt": "2026-11-16T00:00:00Z",
        },
        "RestartCount": 0,
    }
    monkeypatch.setattr(runner, "_inspect_container", lambda _name: observed)

    def docker_command(args, **_kwargs):
        if args[1] == "info":
            return SimpleNamespace(stdout=str(12 * 1024**3))
        return SimpleNamespace(stdout="1GiB / 10GiB")

    monkeypatch.setattr(runner.subprocess, "run", docker_command)
    monkeypatch.setattr(runner, "_health", lambda _endpoint: True)
    monkeypatch.setattr(
        runner,
        "verify_container",
        lambda *_args: {**observed, "Id": "b" * 64},
    )
    journal = tmp_path / "journal.jsonl"
    with journal.open("x", encoding="utf-8") as stream:
        with pytest.raises(ValueError, match="changed while checking boundary"):
            runner._server_boundary(
                stream,
                "local-test",
                tmp_path / "model.gguf",
                {"request_policy": runner.REQUEST, "local_runtime": runner.RUNTIME},
                phase="final",
                completed_cases=32,
            )
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["event"] == "server_boundary"
