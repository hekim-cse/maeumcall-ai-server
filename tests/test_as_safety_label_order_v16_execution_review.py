"""Post-run review tests for the frozen v16 runner's actual stop path."""

from __future__ import annotations

import json
from contextlib import nullcontext

import pytest

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v5 import run as v5
from experiments.as_safety_atomic_edges_v10 import probe
from experiments.as_safety_atomic_edges_v16 import run as v16
from experiments.as_safety_v2.transport import Completion, TransportError


@pytest.mark.parametrize(
    ("outcome", "expected_error", "has_raw"),
    [
        (
            Completion('{"relation_status":"invalid","evidence_clause_index":2}', "stop"),
            "relation_status_invalid",
            True,
        ),
        (
            Completion(
                '{"relation_status":"supported","evidence_clause_index":2,"extra":1}',
                "stop",
            ),
            "fields_invalid",
            True,
        ),
        # The transport rejects whitespace-only content before returning a Completion.
        (TransportError("response_fields_invalid"), "response_fields_invalid", False),
        (TransportError("timeout"), "timeout", False),
    ],
)
def test_runner_stops_after_first_invalid_generation(
    tmp_path, monkeypatch, outcome, expected_error, has_raw
):
    cases = probe.cases()
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    requests = v16._requests(cases, policy)
    journal = tmp_path / "journal.jsonl"
    private = tmp_path / "raw"
    monkeypatch.setattr(v16, "JOURNAL", journal)
    monkeypatch.setattr(v16, "PRIVATE_DIR", private)
    monkeypatch.setattr(
        v16,
        "_load_protocol",
        lambda: ({"max_context_tokens": 4096}, "frozen-protocol", cases, policy, requests),
    )
    monkeypatch.setattr(v16.v12.v10_run, "_server", lambda _: nullcontext(object()))
    monkeypatch.setattr(v16, "guarded_call", lambda _attestor, call: call())
    monkeypatch.setattr(v16.v7, "_tokenize_request", lambda _: 300)
    attempts = []

    def generate(*args, **kwargs):
        attempts.append((args, kwargs))
        if isinstance(outcome, TransportError):
            raise outcome
        return outcome

    monkeypatch.setattr(v16.v4, "post_format_completion", generate)

    v16.run(tmp_path / "unused-model.gguf")

    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert len(attempts) == 1
    assert len(rows) == 2
    assert rows[1]["call"] == "PC01-P014"
    assert rows[1]["error_code"] == expected_error
    assert (private / "PC01-P014.json.txt").exists() is has_raw
    assert not (private / "PC01-P016.json.txt").exists()
