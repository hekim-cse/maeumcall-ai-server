"""Keep each artificial control to exactly one request change."""

import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v5 import run as v5
from experiments.as_safety_atomic_edges_v10 import probe
from experiments.as_safety_atomic_edges_v12 import run as v12
from experiments.as_safety_atomic_edges_v14 import run, verify
from experiments.as_safety_v2.transport import TransportError


def test_each_request_changes_only_its_named_control():
    assert set(run.SOURCES) == verify.SOURCES
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    original = json.loads(v12._requests(probe.cases(), policy)["PC01-P014"])
    for name in run.ORDER:
        variant = json.loads(run._requests(policy)[name])
        assert verify._request(name, policy) == run._requests(policy)[name]
        if name == "schema_forced_unsupported":
            assert variant["response_format"]["schema"]["properties"]["relation_status"][
                "enum"
            ] == ["unsupported"]
            variant["response_format"]["schema"]["properties"]["relation_status"]["enum"] = (
                original["response_format"]["schema"]["properties"]["relation_status"]["enum"]
            )
        else:
            assert (
                variant["messages"][0]["content"]
                == original["messages"][0]["content"] + " " + run.PROMPT_CANARY
            )
            variant["messages"][0]["content"] = original["messages"][0]["content"]
        assert variant == original


def test_verifier_rejects_length_without_error_and_continuation():
    with pytest.raises(ValueError, match="length finish without error"):
        verify._check_rows([{"raw_sha256": "sha", "finish_reason": "length", "error_code": None}])
    with pytest.raises(ValueError, match="continued after error"):
        verify._check_rows(
            [
                {"raw_sha256": "sha", "finish_reason": "length", "error_code": "finish_length"},
                {"raw_sha256": "sha", "finish_reason": "stop", "error_code": None},
            ]
        )


def test_observed_status_is_separate_from_contract_validity():
    raw = b'{"relation_status":"unsupported","evidence_clause_index":null}'
    assert verify._observed_fields(raw) == ("unsupported", None)
    assert verify._observed_fields(b"{") == (None, None)


def _mock_runner(monkeypatch, tmp_path):
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
            {"input_tokens": {name: 1 for name in run.ORDER}},
            "protocol-digest",
            object(),
            {name: b"request" for name in run.ORDER},
        ),
    )
    return journal, private


def test_first_transport_error_stops_without_retry(monkeypatch, tmp_path):
    journal, private = _mock_runner(monkeypatch, tmp_path)
    calls = []

    def fail(*_args, **_kwargs):
        calls.append(1)
        raise TransportError("network_error")

    monkeypatch.setattr(run.v4, "post_format_completion", fail)
    run.run(Path("unused.gguf"))
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert [row.get("call") for row in rows] == [None, run.ORDER[0]]
    assert rows[1]["error_code"] == "network_error"
    assert list(private.iterdir()) == []
    assert calls == [1]
    with pytest.raises(FileExistsError, match="partial control"):
        run.run(Path("unused.gguf"))


@pytest.mark.parametrize(
    ("content", "finish_reason", "expected_error"),
    [
        (
            '{"relation_status":"wrong","evidence_clause_index":2}',
            "stop",
            "relation_status_invalid",
        ),
        (
            '{"relation_status":"unsupported","evidence_clause_index":2,"extra":1}',
            "stop",
            "fields_invalid",
        ),
        (" ", "stop", "invalid_json"),
        ('{"relation_status":"unsupported","evidence_clause_index":2}', "length", "finish_length"),
    ],
)
def test_first_response_error_stops_without_retry(
    monkeypatch, tmp_path, content, finish_reason, expected_error
):
    journal, private = _mock_runner(monkeypatch, tmp_path)
    calls = []

    def respond(*_args, **_kwargs):
        calls.append(1)
        return SimpleNamespace(content=content, finish_reason=finish_reason)

    monkeypatch.setattr(run.v4, "post_format_completion", respond)
    run.run(Path("unused.gguf"))
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert [row.get("call") for row in rows] == [None, run.ORDER[0]]
    assert rows[1]["error_code"] == expected_error
    assert rows[1]["raw_sha256"] is not None
    assert list(private.iterdir()) == [private / f"{run.ORDER[0]}.json.txt"]
    assert calls == [1]
    with pytest.raises(FileExistsError, match="partial control"):
        run.run(Path("unused.gguf"))
    assert calls == [1]


def test_valid_first_response_reaches_second_control(monkeypatch, tmp_path):
    journal, private = _mock_runner(monkeypatch, tmp_path)
    calls = []

    def respond(*_args, **_kwargs):
        calls.append(1)
        return SimpleNamespace(
            content='{"relation_status":"unsupported","evidence_clause_index":2}',
            finish_reason="stop",
        )

    monkeypatch.setattr(run.v4, "post_format_completion", respond)
    run.run(Path("unused.gguf"))
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert [row.get("call") for row in rows] == [None, *run.ORDER]
    assert all(row["error_code"] is None for row in rows[1:])
    assert len(list(private.iterdir())) == 2
    assert calls == [1, 1]


def test_schema_control_does_not_rewrite_prompt():
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    a = run._requests(policy)
    assert a[run.ORDER[0]] != a[run.ORDER[1]]
    assert run._messages_schema(run.ORDER[0])[0] != run._messages_schema(run.ORDER[1])[0]
