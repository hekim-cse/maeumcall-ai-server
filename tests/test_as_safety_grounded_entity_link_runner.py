"""No-model runner checks for the grounded RE/V diagnostic contract."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from scripts import run_as_safety_grounded_entity_link_diagnostic as runner
from scripts.probe_as_safety_clause_index import split_clauses

MESSAGE = "접수할 노트북이 켜지지 않습니다. 친구 태블릿의 충전기에서 연기가 납니다."
CASE = {
    "id": "SYN01",
    "user_message": MESSAGE,
    "expected_relation": {"product_index": 1, "event_status": "observed"},
}
SPAN = {"target_mention": "노트북"}
OWNER = {"clause_index": 2, "mention": "친구 태블릿의 충전기"}


def _response(link: str, evidence: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(
        content=json.dumps({"entity_link": link, "evidence": evidence}, ensure_ascii=False),
        finish_reason="stop",
    )


def _full_quotes() -> list[dict]:
    return [
        {"clause_index": index, "quote": clause}
        for index, clause in enumerate(split_clauses(MESSAGE), 1)
    ]


def test_request_uses_reviewed_anchors_and_journal_retains_only_quote_offsets(monkeypatch):
    calls = []

    def fake_post(_endpoint, _model, messages, _policy, schema):
        calls.append((messages, schema))
        return _response("distinct_item", _full_quotes())

    monkeypatch.setattr(runner, "post_completion", fake_post)
    row = runner._call(CASE, SPAN, OWNER, object())
    assert len(calls) == 1
    messages, schema = calls[0]
    prompt = json.dumps(messages, ensure_ascii=False)
    assert MESSAGE in prompt
    assert SPAN["target_mention"] in prompt and OWNER["mention"] in prompt
    assert "event_status" not in prompt
    assert "accepted_link_kinds" not in prompt
    assert "expected_relation" not in prompt
    assert set(schema["properties"]) == {"entity_link", "evidence"}
    assert schema["properties"]["evidence"]["maxItems"] == 2
    assert (row["entity_link"], row["source_relation"], row["route"]) == (
        "distinct_item",
        "other",
        "collecting_service_request",
    )
    clauses = split_clauses(MESSAGE)
    assert row["evidence_spans"] == [
        {
            "clause_index": index,
            "start": 0,
            "end": len(clause),
            "quote_sha256": hashlib.sha256(clause.encode("utf-8")).hexdigest(),
        }
        for index, clause in enumerate(clauses, 1)
    ]
    serialized = json.dumps(row, ensure_ascii=False)
    assert MESSAGE not in serialized
    assert clauses[0] not in serialized and clauses[1] not in serialized
    assert "quote" not in row["evidence_spans"][0]


def test_unanchored_quote_becomes_unresolved_with_empty_evidence(monkeypatch):
    monkeypatch.setattr(
        runner, "post_completion", lambda *_args: _response("distinct_item", [_full_quotes()[0]])
    )
    row = runner._call(CASE, SPAN, OWNER, object())
    assert (row["entity_link"], row["source_relation"], row["route"]) == (
        "unresolved",
        "unknown",
        "confirming_safety_status",
    )
    assert row["evidence_spans"] == []
    assert row["error_stage"] is None


@pytest.mark.parametrize(
    ("response", "stage", "code"),
    [
        (SimpleNamespace(content="{", finish_reason="stop"), "contract", "invalid_json"),
        (
            SimpleNamespace(content='{"entity_link":"wrong","evidence":[]}', finish_reason="stop"),
            "contract",
            "invalid_relation",
        ),
        (SimpleNamespace(content="unused", finish_reason="length"), "response", "finish_length"),
    ],
)
def test_failure_rows_never_persist_raw_text_or_evidence(monkeypatch, response, stage, code):
    monkeypatch.setattr(runner, "post_completion", lambda *_args: response)
    row = runner._call(CASE, SPAN, OWNER, object())
    assert (row["error_stage"], row["error_code"]) == (stage, code)
    assert row["entity_link"] is row["source_relation"] is row["route"] is None
    assert row["evidence_spans"] == []
    assert MESSAGE not in json.dumps(row, ensure_ascii=False)


def test_isolated_request_policy_allows_320_tokens_and_rejects_old_limit(tmp_path):
    policy_path = runner.SOURCE_PATHS["policy_sha256"]
    policy = runner.load_grounded_policy(policy_path)
    assert policy.max_tokens == 320
    assert policy.timeout_seconds == 180
    assert runner.SOURCE_PATHS["policy_loader_sha256"] == runner.SOURCE_PATHS["runner_sha256"]
    old_limit = json.loads(policy_path.read_text(encoding="utf-8"))
    old_limit["max_tokens"] = 180
    changed_path = tmp_path / "old-limit.json"
    changed_path.write_text(json.dumps(old_limit), encoding="utf-8")
    with pytest.raises(ValueError, match="request policy differs"):
        runner.load_grounded_policy(changed_path)


def test_protocol_must_be_committed_before_model_or_container_call(monkeypatch, tmp_path):
    """A matching local protocol still cannot authorize an uncommitted run."""
    source = tmp_path / "input.txt"
    source.write_bytes(b"source")
    paths = {key: source for key in runner.SOURCE_PATHS}
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "SOURCE_PATHS", paths)
    monkeypatch.setattr(runner, "digest", lambda _path: "a" * 64)
    protocol = {
        "kind": "as_safety_grounded_entity_link_diagnostic_v1",
        "claim_scope": "already_exposed_ai_authored_oracle_diagnostic_only",
        "case_order": runner.CASE_ORDER,
        "endpoint": runner.ENDPOINT,
        "retry_policy": "no_retry_manual_audit_on_interruption",
        "max_tokens": 320,
        "local_runtime": {
            "host_port": 18081,
            "cpu_count": 2,
            "memory_bytes": 4 * 1024**3,
            "context_tokens": 4096,
            "threads": 2,
            "parallel_slots": 1,
        },
        "server_image_digest": runner.IMAGE,
        "model_repo_revision": "b" * 40,
        "model_sha256": "a" * 64,
        **{key: "a" * 64 for key in paths},
    }
    protocol_path = tmp_path / "uncommitted.json"
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")

    def fake_git(command, **_kwargs):
        if command[1] == "status":
            return SimpleNamespace(stdout="")
        if command[2] == "HEAD:uncommitted.json":
            return SimpleNamespace(stdout=b"")
        return SimpleNamespace(stdout=b"source")

    monkeypatch.setattr(runner.subprocess, "run", fake_git)
    with pytest.raises(ValueError, match="protocol is not committed"):
        runner.validate_protocol(protocol_path, source, source, source, source)
