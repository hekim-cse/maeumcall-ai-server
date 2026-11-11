"""Exercise the gold-owner oracle boundary and independent journal checks."""

from __future__ import annotations

import copy
import hashlib
import json
import urllib.error
from types import SimpleNamespace

import pytest

from scripts import audit_as_safety_gold_owner_link_journal as postrun_audit
from scripts import run_as_safety_gold_owner_link_diagnostic as runner
from scripts import verify_as_safety_gold_owner_link_diagnostic as verifier

ORIGINAL_REQUIRE_COMMITTED = verifier._require_committed


@pytest.fixture(autouse=True)
def _synthetic_journal_needs_no_git_commit(monkeypatch):
    monkeypatch.setattr(verifier, "_require_committed", lambda _path: None)


def _inputs():
    return runner.load_gold_owner_cases(
        runner.SOURCE_PATHS["spans_sha256"], runner.SOURCE_PATHS["owner_labels_sha256"]
    )


def _protocol():
    return {
        "kind": "as_safety_gold_owner_link_diagnostic_v1",
        "claim_scope": "already_exposed_ai_authored_oracle_diagnostic_only",
        "case_order": runner.CASE_ORDER,
        "retry_policy": "no_retry_manual_audit_on_interruption",
        "endpoint": "http://127.0.0.1:18081/v1/chat/completions",
        "server_image_digest": "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35",
        "max_tokens": 180,
        "local_runtime": {
            "host_port": 18081,
            "cpu_count": 2,
            "memory_bytes": 4 * 1024**3,
            "context_tokens": 4096,
            "threads": 2,
            "parallel_slots": 1,
        },
        "model_sha256": "a" * 64,
        "model_repo_revision": "a" * 40,
        **{key: verifier.digest(path) for key, path in verifier.SOURCES.items()},
    }


def _journal(tmp_path, protocol, predictions=None):
    protocol_path = tmp_path / "protocol.json"
    raw = json.dumps(protocol, ensure_ascii=False).encode()
    protocol_path.write_bytes(raw)
    cases = verifier._reviewed_cases()
    rows = [{"event": "header", "protocol_sha256": hashlib.sha256(raw).hexdigest()}]
    for case in cases:
        relation = (predictions or {}).get(case["id"], case["gold_relation"])
        rows.append({"event": "begin", "case_id": case["id"]})
        rows.append(
            {
                "event": "end",
                "case_id": case["id"],
                "source_relation": relation,
                "route": verifier._route(relation, case["event_status"]),
                "error_stage": None,
                "error_code": None,
                "http_status": None,
                "finish_reason": "stop",
                "latency_ms": 1.25,
            }
        )
    journal_path = tmp_path / "journal.jsonl"
    journal_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return protocol_path, journal_path, rows


def test_selection_is_reviewed_22_with_overlay_and_conditional_event():
    selected = _inputs()
    assert len(selected) == 22
    assert tuple(case["id"] for case, _, _ in selected) == runner.CASE_IDS
    assert {"RE07", "V09"}.isdisjoint(runner.CASE_IDS)
    by_id = {case["id"]: (case, span, owner) for case, span, owner in selected}
    assert by_id["RE06"][0]["expected_relation"]["event_status"] == "uncertain"
    assert by_id["RE06"][2] == {"clause_index": 1, "mention": "커피머신 물통"}
    assert by_id["V04"][1]["reviewed_interpretation"]["target_relation"] == "current"
    assert by_id["V04"][1]["target_mention"] == "토스터"
    assert {"current": 16, "other": 6} == {
        relation: sum(
            span.get("reviewed_interpretation", {}).get(
                "target_relation", case["expected_relation"]["target_relation"]
            )
            == relation
            for case, span, _ in selected
        )
        for relation in ("current", "other")
    }


def test_one_call_exposes_owner_anchor_but_not_relation_or_link_kind(monkeypatch):
    case, span, owner = _inputs()[0]
    calls = []

    def fake_post(_endpoint, _model, messages, _policy, schema):
        calls.append((messages, schema))
        return SimpleNamespace(content='{"source_relation":"current"}', finish_reason="stop")

    monkeypatch.setattr(runner, "post_completion", fake_post)
    row = runner._call(case, span, owner, object())
    assert len(calls) == 1
    messages, schema = calls[0]
    prompt = json.dumps(messages, ensure_ascii=False)
    assert owner["mention"] in prompt
    assert "accepted_link_kinds" not in prompt
    assert "part_or_anaphora" not in prompt
    assert "expected_relation" not in prompt
    assert set(schema["properties"]) == {"source_relation"}
    assert row["source_relation"] == "current"
    assert case["user_message"] not in json.dumps(row, ensure_ascii=False)
    assert owner["mention"] not in json.dumps(row, ensure_ascii=False)
    verifier._check_end(row, verifier._reviewed_cases()[0])


def test_one_call_routes_other_to_service_request(monkeypatch):
    """Check the real runner route without a synthesized verifier journal."""
    case, span, owner = _inputs()[0]
    monkeypatch.setattr(
        runner,
        "post_completion",
        lambda *_args: SimpleNamespace(content='{"source_relation":"other"}', finish_reason="stop"),
    )
    row = runner._call(case, span, owner, object())
    assert row["source_relation"] == "other"
    assert row["route"] == "collecting_service_request"


def test_commit_check_rejects_working_file_mismatch(monkeypatch):
    """Exercise the commit guard that synthetic journal tests bypass."""
    monkeypatch.setattr(verifier, "_require_committed", ORIGINAL_REQUIRE_COMMITTED)
    monkeypatch.setattr(
        verifier.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(stdout=b"wrong")
    )
    with pytest.raises(ValueError, match="not committed"):
        verifier._require_committed(
            verifier.ROOT / "scripts/verify_as_safety_gold_owner_link_diagnostic.py"
        )


@pytest.mark.parametrize(
    ("response", "stage", "code", "finish", "status"),
    [
        (
            SimpleNamespace(content="{", finish_reason="stop"),
            "contract",
            "invalid_json",
            "stop",
            None,
        ),
        (
            SimpleNamespace(content='{"source_relation":"bad"}', finish_reason="stop"),
            "contract",
            "invalid_relation",
            "stop",
            None,
        ),
        (
            SimpleNamespace(content='{"source_relation":"current"}', finish_reason="length"),
            "response",
            "finish_length",
            "length",
            None,
        ),
        (
            urllib.error.HTTPError("http://127.0.0.1/", 503, "private body", None, None),
            "response",
            "http_error",
            None,
            503,
        ),
    ],
)
def test_failure_is_finite_and_never_persists_response(
    monkeypatch, response, stage, code, finish, status
):
    case, span, owner = _inputs()[0]
    calls = 0

    def fake_post(*_args):
        nonlocal calls
        calls += 1
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(runner, "post_completion", fake_post)
    row = runner._call(case, span, owner, object())
    assert calls == 1
    assert (row["error_stage"], row["error_code"], row["finish_reason"], row["http_status"]) == (
        stage,
        code,
        finish,
        status,
    )
    assert row["source_relation"] is None and row["route"] is None
    assert "private body" not in json.dumps(row)
    verifier._check_end(row, verifier._reviewed_cases()[0])


def test_independent_45_row_audit_reports_denominators_and_sensitivity(tmp_path):
    protocol_path, journal_path, _rows = _journal(tmp_path, _protocol(), {"V16": "unknown"})
    result = verifier.verify(protocol_path, journal_path)
    assert result["summary"]["all"]["denominator"] == 22
    assert result["summary"]["all"]["relation_correct"] == 21
    assert result["summary"]["all"]["unknown_outputs"] == 1
    assert result["by_gold_relation"]["current"]["denominator"] == 16
    assert result["by_gold_relation"]["other"]["denominator"] == 6
    assert result["summary"]["sensitivity_excluding_V03_V04"]["denominator"] == 20
    assert result["summary"]["sensitivity_excluding_RE06"]["denominator"] == 21
    assert len(result["contrast_pairs"]) == 3
    assert result["development_thresholds"]["met"]


@pytest.mark.parametrize(
    "mutation", ["duplicate", "nonfinite", "extra_field", "order", "route", "row_count"]
)
def test_journal_rejects_tampering_before_reporting_metrics(tmp_path, mutation):
    protocol_path, journal_path, rows = _journal(tmp_path, _protocol())
    changed = copy.deepcopy(rows)
    if mutation == "duplicate":
        lines = journal_path.read_text(encoding="utf-8").splitlines()
        lines[2] = lines[2].replace(
            '"source_relation": "current"',
            '"source_relation": "other", "source_relation": "current"',
        )
        journal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif mutation == "nonfinite":
        lines = journal_path.read_text(encoding="utf-8").splitlines()
        lines[2] = lines[2].replace('"latency_ms": 1.25', '"latency_ms": NaN')
        journal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        if mutation == "extra_field":
            changed[2]["raw_response"] = "secret"
        elif mutation == "order":
            changed[1]["case_id"] = "V01"
        elif mutation == "route":
            changed[2]["route"] = "collecting_service_request"
        else:
            changed.pop()
        journal_path.write_text(
            "\n".join(json.dumps(row) for row in changed) + "\n", encoding="utf-8"
        )
    with pytest.raises(ValueError):
        verifier.verify(protocol_path, journal_path)


def test_source_hash_tamper_rejected(tmp_path):
    protocol = _protocol()
    protocol["candidate_sha256"] = "0" * 64
    protocol_path, journal_path, _rows = _journal(tmp_path, protocol)
    with pytest.raises(ValueError, match="frozen candidate"):
        verifier.verify(protocol_path, journal_path)


@pytest.mark.parametrize("mutated", ['{"kind":"first","kind":"second"}', '{"kind":NaN}'])
def test_runner_rejects_invalid_protocol_before_model_call(tmp_path, mutated):
    path = tmp_path / "protocol.json"
    path.write_text(mutated, encoding="utf-8")
    with pytest.raises(ValueError):
        runner.validate_protocol(path, path, path, path, path)


def test_postrun_audit_accepts_original_and_rejects_exception_finish_reason(tmp_path):
    """Preserve the frozen run and reject a review-discovered journal mutation."""
    data = verifier.DATA
    protocol = data / "as-safety-gold-owner-link-diagnostic-protocol.v1.json"
    original = data / "as-safety-gold-owner-link-diagnostic-journal.v1.jsonl"
    assert postrun_audit.audit(protocol, original)["relation_correct"] == 16
    lines = original.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[2])
    row.update(
        {
            "source_relation": None,
            "route": None,
            "error_stage": "response",
            "error_code": "transport_error",
            "finish_reason": "stop",
        }
    )
    lines[2] = json.dumps(row)
    mutated = tmp_path / "mutated.jsonl"
    mutated.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="response exception has finish reason"):
        postrun_audit.audit(protocol, mutated)


def test_postrun_audit_rejects_blank_mentions():
    """Reject review annotations made only of whitespace."""
    assert not postrun_audit._nonblank(" \t")
    assert not postrun_audit._nonblank(None)
    assert postrun_audit._nonblank("커피머신 물통")
