"""Post-run coverage for invalid responses and interrupted evidence runs."""

import json
from contextlib import nullcontext

import pytest

from experiments.as_safety_atomic_edges_v17 import evidence_contract
from experiments.as_safety_atomic_edges_v17 import run as v17
from experiments.as_safety_atomic_edges_v18 import run as v18
from experiments.as_safety_atomic_edges_v18 import selection
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.transport import Completion, TransportError


@pytest.mark.parametrize(
    ("runner", "contract", "changes", "code"),
    [
        (
            v17,
            evidence_contract,
            {"source_evidence": {"clause_index": 99, "quote": "x"}},
            "quote_index_invalid",
        ),
        (v17, evidence_contract, {"extra": 1}, "fields_invalid"),
        (
            v17,
            evidence_contract,
            {"source_evidence": {"clause_index": 2, "quote": "x", "extra": 1}},
            "quote_fields_invalid",
        ),
        (
            v17,
            evidence_contract,
            {"source_evidence": {"clause_index": 2, "quote": ""}},
            "quote_blank",
        ),
        (
            v17,
            evidence_contract,
            {"source_evidence": {"clause_index": 2, "quote": " "}},
            "quote_blank",
        ),
        (v18, selection, {"extra": 1}, "fields_invalid"),
        (v18, selection, {"source_evidence": " "}, "evidence_candidate_not_offered"),
    ],
)
def test_evidence_contract_rejects_invalid_output(runner, contract, changes, code):
    _, calls = runner.calls()
    pair = next(iter(calls.values()))[0]
    raw = dict.fromkeys(("source_evidence", "exclusion_evidence", "uncertainty_evidence"))
    with pytest.raises(ValidationError, match=code):
        contract.validate_response(json.dumps(raw | changes), pair)


@pytest.mark.parametrize("runner", [v17, v18])
@pytest.mark.parametrize("error", ["timeout", "fields_invalid"])
def test_execution_stops_without_retry_and_replay_marks_remaining_calls(
    runner, error, monkeypatch, tmp_path
):
    journal = tmp_path / "journal.jsonl"
    monkeypatch.setattr(runner, "JOURNAL", journal)
    monkeypatch.setattr(runner, "PRIVATE_DIR", tmp_path / "raw")
    monkeypatch.setattr(runner.v12, "_clean", lambda: None)
    monkeypatch.setattr(runner, "load_protocol", lambda _requests, **kwargs: "frozen")
    monkeypatch.setattr(runner.v12.v10_run, "_server", lambda _: nullcontext(object()))
    monkeypatch.setattr(runner, "guarded_call", lambda _attestor, call: call())
    monkeypatch.setattr(runner.v7, "_tokenize_request", lambda _: 300)
    attempts = []

    def generate(*args, **kwargs):
        attempts.append((args, kwargs))
        if error == "timeout":
            raise TransportError(error)
        return Completion("{}", "stop")

    monkeypatch.setattr(runner.v4, "post_format_completion", generate)
    model_path = tmp_path / "unused.gguf"
    runner.run(model_path)
    with pytest.raises(FileExistsError, match="partial run"):
        runner.run(model_path)
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert len(attempts) == 1
    assert len(rows) == 2
    assert rows[1]["error_code"] == error
    if runner is v18:
        scores = runner.replay()
        assert [row["call"] for row in scores] == list(runner.calls()[1])
        assert scores[0]["error"] == error
        assert scores[0]["gold_evidence_selected_if_offered"] is False
        assert all(row["execution_status"] == "not_run" for row in scores[1:])
        assert all(row["gold_candidate_offered"] is True for row in scores[1:])
        assert all(row["gold_evidence_selected_if_offered"] is None for row in scores[1:])
        assert all(row["status_match"] is None for row in scores[1:])
