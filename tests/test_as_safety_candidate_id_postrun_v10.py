"""Post-run regressions without changing the frozen execution tests."""

import json
from contextlib import nullcontext
from pathlib import Path

import pytest

from experiments.as_safety_atomic_edges_v10 import probe, run, verify
from experiments.as_safety_v2.transport import TransportError


@pytest.mark.parametrize(
    "raw",
    [
        b'{"candidate_id":"P014","event_subject_kind":"invalid"}',
        b'{"candidate_id":"P014","event_subject_kind":"location","extra":1}',
        b"   ",
    ],
)
def test_independent_verifier_rejects_invalid_model_outputs(raw):
    assert verify._score(raw, probe.cases()["PC01"])["contract_valid"] is False


def test_first_transport_error_stops_and_prevents_restart(monkeypatch, tmp_path):
    journal = tmp_path / "journal.jsonl"
    private = tmp_path / "raw"
    monkeypatch.setattr(run, "JOURNAL", journal)
    monkeypatch.setattr(run, "PRIVATE_DIR", private)
    monkeypatch.setattr(run, "_server", lambda _path: nullcontext(object()))
    monkeypatch.setattr(run, "guarded_call", lambda _attestor, call: call())
    monkeypatch.setattr(run.v7, "_tokenize_request", lambda _body: 1)
    monkeypatch.setattr(
        run,
        "_load_protocol",
        lambda: (
            {"input_tokens": {"PC01": 1, "NC01": 1}},
            "protocol-digest",
            probe.cases(),
            object(),
            {"PC01": b"first", "NC01": b"second"},
        ),
    )
    calls = []

    def fail_first(*_args, **_kwargs):
        calls.append("model")
        raise TransportError("network_unavailable")

    monkeypatch.setattr(run.v4, "post_format_completion", fail_first)
    run.run(Path("unused.gguf"))
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert [row.get("call") for row in rows] == [None, "PC01"]
    assert rows[1]["error_code"] == "network_unavailable"
    assert rows[1]["raw_sha256"] is None
    assert calls == ["model"]

    with pytest.raises(FileExistsError, match="partial run"):
        run.run(Path("unused.gguf"))
    assert calls == ["model"]
