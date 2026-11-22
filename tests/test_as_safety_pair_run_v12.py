"""Prevent request drift, label leakage, and partial-run retries."""

import copy
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v5 import run as v5
from experiments.as_safety_atomic_edges_v10 import probe
from experiments.as_safety_atomic_edges_v12 import run, verify
from experiments.as_safety_v2.transport import TransportError


def test_independent_request_builder_matches_and_ignores_gold():
    cases = probe.cases()
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    baseline = run._requests(cases, policy)
    assert list(baseline) == ["PC01-P014", "PC01-P016", "NC01-P020", "NC01-P002"]
    assert all(
        verify._request(cases[case_id], candidate_id, policy) == baseline[name]
        for name in baseline
        for case_id, candidate_id in [name.split("-", 1)]
    )
    altered = copy.deepcopy(cases)
    for case in altered.values():
        case["gold_subject_span"] = None
        case["gold_kind"] = "unresolved"
    assert run._requests(altered, policy) == baseline


def test_verifier_separates_contract_from_user_reviewed_status():
    gold = {"relation_status": "supported", "evidence_clause_index": 2}
    assert verify._score(
        b'{"relation_status":"unsupported","evidence_clause_index":2}', 2, gold
    ) == {
        "contract_valid": True,
        "contract_error": None,
        "relation_status": "unsupported",
        "status_exact": False,
        "evidence_clause_exact": True,
    }
    assert (
        verify._score(b'{"relation_status":"supported","evidence_clause_index":null}', 2, gold)[
            "contract_valid"
        ]
        is False
    )


def test_first_transport_error_stops_without_retry(monkeypatch, tmp_path):
    journal = tmp_path / "journal.jsonl"
    private = tmp_path / "raw"
    monkeypatch.setattr(run, "JOURNAL", journal)
    monkeypatch.setattr(run, "PRIVATE_DIR", private)
    monkeypatch.setattr(run.v10_run, "_server", lambda _path: nullcontext(object()))
    monkeypatch.setattr(run, "guarded_call", lambda _attestor, call: call())
    monkeypatch.setattr(run.v7, "_tokenize_request", lambda _body: 1)
    cases = probe.cases()
    requests = {
        name: name.encode() for name in ("PC01-P014", "PC01-P016", "NC01-P020", "NC01-P002")
    }
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
    calls = []

    def fail(*_args, **_kwargs):
        calls.append(1)
        raise TransportError("network_unavailable")

    monkeypatch.setattr(run.v4, "post_format_completion", fail)
    run.run(Path("unused.gguf"))
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert [row.get("call") for row in rows] == [None, "PC01-P014"]
    assert rows[1]["error_code"] == "network_unavailable"
    assert calls == [1]
    with pytest.raises(FileExistsError, match="partial run"):
        run.run(Path("unused.gguf"))
    assert calls == [1]


def test_first_contract_error_saves_raw_and_stops_without_retry(monkeypatch, tmp_path):
    journal = tmp_path / "journal.jsonl"
    private = tmp_path / "raw"
    monkeypatch.setattr(run, "JOURNAL", journal)
    monkeypatch.setattr(run, "PRIVATE_DIR", private)
    monkeypatch.setattr(run.v10_run, "_server", lambda _path: nullcontext(object()))
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
    calls = []

    def malformed(*_args, **_kwargs):
        calls.append(1)
        return SimpleNamespace(
            finish_reason="stop",
            content='{"relation_status":"supported","evidence_clause_index":null}',
        )

    monkeypatch.setattr(run.v4, "post_format_completion", malformed)
    run.run(Path("unused.gguf"))
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert [row.get("call") for row in rows] == [None, "PC01-P014"]
    assert rows[1]["error_code"] == "evidence_clause_missing"
    assert rows[1]["raw_sha256"] is not None
    assert (private / "PC01-P014.json.txt").exists()
    assert calls == [1]
    with pytest.raises(FileExistsError, match="partial run"):
        run.run(Path("unused.gguf"))
    assert calls == [1]
