"""Exercise the common runner without a local model or Docker."""

from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments import as_safety_runner as runner
from experiments.as_safety_v2.transport import Completion, TransportError


@pytest.fixture
def experiment(monkeypatch, tmp_path):
    monkeypatch.setattr(runner.repo, "_clean", lambda: None)
    monkeypatch.setattr(runner.Experiment, "protocol_digest", lambda _: "frozen")
    monkeypatch.setattr(runner, "guarded_call", lambda _, call: call())
    monkeypatch.setattr(runner.tokenizer, "_tokenize_request", lambda _: 200)
    monkeypatch.setattr(runner, "verify_container", lambda *_: None)
    model = runner.Model(
        "a" * 64,
        "test",
        lambda path: nullcontext(
            SimpleNamespace(
                expected_sha256="a" * 64,
                container_name="test",
                path=path.resolve(),
            )
        ),
    )
    policy = runner.journal_io._policy({"request_policy": runner.execution.REQUEST_POLICY})
    calls = tuple(runner.Call(name, [], {}, int) for name in ("first", "second"))
    result = runner.Experiment("test-runner", model, policy, calls, (), {})
    result.journal = tmp_path / "journal"
    result.private = tmp_path / "raw"
    return result


def test_success_replay_and_raw_tamper_detection(monkeypatch, experiment):
    monkeypatch.setattr(
        runner.wire, "post_format_completion", lambda *a, **kw: Completion("2", "stop")
    )
    experiment.run(Path("unused"))
    rows = experiment.replay()
    assert [row["selected"] for row in rows] == [2, 2]
    (experiment.private / "first.json.txt").write_text("1", encoding="utf-8")
    with pytest.raises(ValueError, match="raw response differs"):
        experiment.replay()


def test_transport_error_stops_after_one_attempt(monkeypatch, experiment):
    attempts = []

    def fail(*args, **kwargs):
        attempts.append(1)
        raise TransportError("timeout")

    monkeypatch.setattr(runner.wire, "post_format_completion", fail)
    experiment.run(Path("unused"))
    assert [row["error"] for row in experiment.replay()] == ["timeout"]
    assert attempts == [1]
    with pytest.raises(FileExistsError, match="partial run"):
        experiment.run(Path("unused"))
    assert attempts == [1]


def test_runner_rejects_adapter_for_a_different_model(experiment):
    model = experiment.model
    experiment.model = runner.Model("b" * 64, model.container, model.server)
    with pytest.raises(ValueError, match="running model differs"):
        experiment.run(Path("unused"))
    assert not experiment.journal.exists()


def test_protocol_must_match_committed_bytes(monkeypatch, tmp_path):
    policy = runner.journal_io._policy({"request_policy": runner.execution.REQUEST_POLICY})
    model = runner.Model("a" * 64, "test", lambda _: nullcontext())
    experiment = runner.Experiment(
        "test-runner", model, policy, (runner.Call("first", [], {}, int),), (), {}
    )
    experiment.protocol = tmp_path / "protocol.json"
    experiment.protocol.write_text('{"commit":"abc"}\n')
    monkeypatch.setattr(runner.repo, "ROOT", tmp_path)
    monkeypatch.setattr(experiment, "manifest", lambda commit: {"commit": commit})
    monkeypatch.setattr(runner.repo, "_git", lambda *args: b'{"commit":"previous"}\n')
    with pytest.raises(ValueError, match="committed before calls"):
        experiment.protocol_digest()
    monkeypatch.setattr(runner.repo, "_git", lambda *args: experiment.protocol.read_bytes())
    assert experiment.protocol_digest() == runner.repo._sha(experiment.protocol.read_bytes())
