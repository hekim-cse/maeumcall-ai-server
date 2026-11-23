"""Preserve the separate one-call prompt control after v14 stopped early."""

import json
from contextlib import nullcontext
from pathlib import Path

import pytest

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v5 import run as v5
from experiments.as_safety_atomic_edges_v10 import probe
from experiments.as_safety_atomic_edges_v12 import run as v12
from experiments.as_safety_atomic_edges_v14 import verify as v14_verify
from experiments.as_safety_atomic_edges_v15 import run, verify
from experiments.as_safety_v2.transport import TransportError


def test_only_system_message_changes_from_baseline():
    assert set(run.SOURCES) == verify.SOURCES
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    baseline = json.loads(v12._requests(probe.cases(), policy)["PC01-P014"])
    variant = json.loads(run._request(policy))
    assert verify.v14_verify._request(run.CALL, policy) == run._request(policy)
    assert (
        variant["messages"][0]["content"]
        == baseline["messages"][0]["content"] + " " + v14_verify.PROMPT_CANARY
    )
    variant["messages"][0]["content"] = baseline["messages"][0]["content"]
    assert variant == baseline


def test_first_transport_failure_blocks_retry(monkeypatch, tmp_path):
    journal = tmp_path / "journal.jsonl"
    private = tmp_path / "raw"
    monkeypatch.setattr(run, "JOURNAL", journal)
    monkeypatch.setattr(run, "PRIVATE_DIR", private)
    monkeypatch.setattr(run.v12.v10_run, "_server", lambda _path: nullcontext(object()))
    monkeypatch.setattr(run, "guarded_call", lambda _attestor, call: call())
    monkeypatch.setattr(run.v7, "_tokenize_request", lambda _body: 1)
    monkeypatch.setattr(
        run,
        "_load_protocol",
        lambda: (
            {"input_tokens": 1},
            "protocol-digest",
            object(),
            b"request",
        ),
    )
    calls = []

    def fail(*_args, **_kwargs):
        calls.append(1)
        raise TransportError("network_error")

    monkeypatch.setattr(run.v4, "post_format_completion", fail)
    run.run(Path("unused.gguf"))
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert len(rows) == 2
    assert rows[1]["error_code"] == "network_error"
    assert list(private.iterdir()) == []
    assert calls == [1]
    with pytest.raises(FileExistsError, match="partial control"):
        run.run(Path("unused.gguf"))


@pytest.mark.parametrize("invalid", ["invalid", " ", "extra_field"])
def test_invalid_protocol_is_rejected_before_model_call(monkeypatch, tmp_path, invalid):
    payload = json.loads(run.PROTOCOL.read_text())
    if invalid == "extra_field":
        payload["unexpected"] = True
    else:
        payload["call"] = invalid
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(payload))
    monkeypatch.setattr(run, "PROTOCOL", path)
    monkeypatch.setattr(verify, "PROTOCOL", path)
    monkeypatch.setattr(run, "JOURNAL", tmp_path / "journal.jsonl")
    monkeypatch.setattr(run, "PRIVATE_DIR", tmp_path / "raw")
    calls = []

    def forbidden(*_args, **_kwargs):
        calls.append(1)
        raise AssertionError("model must not be called")

    monkeypatch.setattr(run.v12.v10_run, "_server", forbidden)
    monkeypatch.setattr(run.v7, "_tokenize_request", forbidden)
    with pytest.raises(ValueError, match="protocol identity differs"):
        run.run(Path("unused.gguf"))
    with pytest.raises(ValueError, match="protocol identity differs"):
        verify.verify()
    assert calls == []
