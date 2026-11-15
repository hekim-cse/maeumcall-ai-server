"""The exposed development baseline must not be mistaken for a fresh test."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.structured_nlu.schema import CasePrediction, EvaluationAttempt
from experiments.nlu_current_baseline_v1 import run as runner


def test_reviewed_input_is_exposed_balanced_development() -> None:
    reviewed = runner._reviewed()
    assert len(reviewed.dataset.cases) == 32
    assert set(reviewed.scenario_counts.values()) == {2}
    assert [case.id for case in reviewed.dataset.cases] == [
        f"ai-heldout-ah{i:02}" for i in range(1, 33)
    ]
    assert runner.SCOPE.endswith("development_only")


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
        "case_order": [case.id for case in reviewed.dataset.cases],
    }
    monkeypatch.setattr(runner, "load_protocol", lambda *_args: (protocol, "f" * 64))
    monkeypatch.setattr(runner.v4, "verify_container", lambda *_args: None)
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
    assert len(rows) == 66
    assert rows[0] == {"event": "header", "protocol_sha256": "f" * 64}
    assert rows[-1] == {"event": "summary", "summary": result["summary"]}
    assert result["journal_sha256"] == runner._file_sha(journal)
    assert rows[2]["raw_attempts"] == [
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
        "case_order": [case.id for case in reviewed.dataset.cases],
    }
    monkeypatch.setattr(runner, "load_protocol", lambda *_args: (protocol, "f" * 64))
    monkeypatch.setattr(runner.v4, "verify_container", lambda *_args: None)
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
        "case_order": [case.id for case in reviewed.dataset.cases],
    }
    monkeypatch.setattr(runner, "load_protocol", lambda *_args: (protocol, "f" * 64))
    monkeypatch.setattr(runner.v4, "verify_container", lambda *_args: None)
    monkeypatch.setattr(
        runner, "_post_completion", lambda *_args: (_ for _ in ()).throw(OSError("secret"))
    )

    def fake_case(case, *, endpoint, model_id, policy, completion_post):
        try:
            completion_post(endpoint, model_id, [], policy)
        except OSError:
            pass
        return CasePrediction(
            case_id=case.id,
            attempts=(EvaluationAttempt(contract_valid=False, latency_ms=1, error_type="OSError"),),
        )

    monkeypatch.setattr(runner, "_run_case", fake_case)
    output = tmp_path / "result.json"
    journal = tmp_path / "journal.jsonl"
    private_dir = tmp_path / "raw"
    runner.run(
        protocol_path=tmp_path / "protocol.json",
        model_path=tmp_path / "model.gguf",
        output=output,
        journal=journal,
        private_dir=private_dir,
        container_name="local-test",
    )
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert rows[2]["raw_attempts"] == [
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
