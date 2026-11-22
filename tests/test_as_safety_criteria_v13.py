"""Check the one-variable request contrast and stop-on-first-error behavior."""

import copy
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v5 import run as v5
from experiments.as_safety_atomic_edges_v10 import probe
from experiments.as_safety_atomic_edges_v12 import run as v12
from experiments.as_safety_atomic_edges_v12 import verify as v12_verify
from experiments.as_safety_atomic_edges_v13 import run, verify
from experiments.as_safety_v2.transport import TransportError


def test_only_system_criterion_changes_and_gold_is_not_sent():
    assert set(run.SOURCES) == verify.SOURCES
    cases = probe.cases()
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    variant = run._requests(cases, policy)
    baseline = v12._requests(cases, policy)
    assert list(variant) == ["PC01-P014", "PC01-P016", "NC01-P020", "NC01-P002"]
    for name, raw in variant.items():
        old = json.loads(baseline[name])
        new = json.loads(raw)
        assert new["messages"][0]["content"] == old["messages"][0]["content"] + " " + run.CRITERION
        new["messages"][0]["content"] = old["messages"][0]["content"]
        assert new == old
        case_id, candidate_id = name.split("-", 1)
        assert verify._request(cases[case_id], candidate_id, policy) == raw
    altered = copy.deepcopy(cases)
    for case in altered.values():
        case["gold_subject_span"] = None
        case["gold_kind"] = "unresolved"
    assert run._requests(altered, policy) == variant


@pytest.fixture
def mocked_runner(monkeypatch, tmp_path):
    journal = tmp_path / "journal.jsonl"
    private = tmp_path / "raw"
    monkeypatch.setattr(run, "JOURNAL", journal)
    monkeypatch.setattr(run, "PRIVATE_DIR", private)
    monkeypatch.setattr(run.v12.v10_run, "_server", lambda _path: nullcontext(object()))
    monkeypatch.setattr(run, "guarded_call", lambda _attestor, call: call())
    monkeypatch.setattr(run.v7, "_tokenize_request", lambda _body: 1)
    cases = probe.cases()
    requests = {f"{case}-{candidate}": b"request" for case, candidate in run.ORDER}
    monkeypatch.setattr(
        run,
        "_load_protocol",
        lambda: (
            {"input_tokens": {name: 1 for name in requests}},
            "protocol-digest",
            cases,
            object(),
            requests,
        ),
    )
    return journal, private


@pytest.mark.parametrize(
    ("content", "error_code"),
    [
        ('{"relation_status":"supported","evidence_clause_index":null}', "evidence_clause_missing"),
        ('{"relation_status":"wrong","evidence_clause_index":2}', "relation_status_invalid"),
        ('{"relation_status":"supported","evidence_clause_index":2,"extra":1}', "fields_invalid"),
        (" ", "invalid_json"),
    ],
)
def test_first_contract_error_saves_raw_and_stops_without_retry(
    monkeypatch, mocked_runner, content, error_code
):
    journal, private = mocked_runner
    calls = []

    def malformed(*_args, **_kwargs):
        calls.append(1)
        return SimpleNamespace(finish_reason="stop", content=content)

    monkeypatch.setattr(run.v4, "post_format_completion", malformed)
    run.run(Path("unused.gguf"))
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert [row.get("call") for row in rows] == [None, "PC01-P014"]
    assert rows[1]["error_code"] == error_code
    assert rows[1]["raw_sha256"] is not None
    assert (private / "PC01-P014.json.txt").exists()
    assert calls == [1]
    with pytest.raises(FileExistsError, match="partial run"):
        run.run(Path("unused.gguf"))
    assert calls == [1]


def test_first_transport_error_stops_without_raw_or_retry(monkeypatch, mocked_runner):
    journal, private = mocked_runner
    calls = []

    def failed_transport(*_args, **_kwargs):
        calls.append(1)
        raise TransportError("network_error")

    monkeypatch.setattr(run.v4, "post_format_completion", failed_transport)
    run.run(Path("unused.gguf"))
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert [row.get("call") for row in rows] == [None, "PC01-P014"]
    assert rows[1]["error_code"] == "network_error"
    assert rows[1]["raw_sha256"] is None
    assert list(private.iterdir()) == []
    assert calls == [1]
    with pytest.raises(FileExistsError, match="partial run"):
        run.run(Path("unused.gguf"))
    assert calls == [1]


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ([{"raw_sha256": "sha", "finish_reason": "length", "error_code": None}], "finish_length"),
        (
            [
                {"raw_sha256": "sha", "finish_reason": "length", "error_code": "finish_length"},
                {"raw_sha256": "sha", "finish_reason": "stop", "error_code": None},
            ],
            "continued after error",
        ),
        ([{"raw_sha256": "sha", "finish_reason": None, "error_code": None}], "finish reason"),
    ],
)
def test_verifier_rejects_impossible_journal_termination(rows, message):
    with pytest.raises(ValueError, match=message):
        verify._check_result_rows(rows)


def test_verifier_accepts_success_rows_and_terminal_length_error():
    verify._check_result_rows(
        [
            {"raw_sha256": "sha", "finish_reason": "stop", "error_code": None},
            {"raw_sha256": "sha", "finish_reason": "length", "error_code": "finish_length"},
        ]
    )


def test_independent_baseline_request_builder_remains_distinct():
    cases = probe.cases()
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    assert all(
        verify._request(cases[case_id], candidate_id, policy)
        != v12_verify._request(cases[case_id], candidate_id, policy)
        for case_id, candidate_id in run.ORDER
    )
