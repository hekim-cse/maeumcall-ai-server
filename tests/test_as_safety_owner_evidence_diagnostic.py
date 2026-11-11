"""Check the reviewed-label gate, one-call journal, and independent audit."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_as_safety_owner_evidence_diagnostic as runner
from scripts import verify_as_safety_owner_evidence_diagnostic as verifier
from scripts.probe_as_safety_clause_index import split_clauses


def _synthetic_labels(tmp_path: Path):
    """Build structural test labels, not actual reviewed semantic annotations."""
    paired = runner.load_active_cases(runner.SOURCE_PATHS["spans_sha256"])
    labels = []
    for case, span in paired:
        relation = span.get("reviewed_interpretation", {}).get(
            "target_relation", case["expected_relation"]["target_relation"]
        )
        if relation == "unknown":
            kinds, accepted = ["unresolved"], []
        elif relation == "other":
            kinds = ["explicit_other"]
            accepted = [
                {
                    "clause_index": case["expected_relation"]["hazard_index"],
                    "mention": span["hazard_event_mention"],
                }
            ]
        else:
            kinds = ["same_entity"]
            accepted = [
                {
                    "clause_index": case["expected_relation"]["product_index"],
                    "mention": span["target_mention"],
                }
            ]
        labels.append(
            {
                "id": case["id"],
                "accepted_owner_spans": accepted,
                "accepted_link_kinds": kinds,
            }
        )
    path = tmp_path / "synthetic-reviewed-labels.json"
    path.write_text(
        json.dumps(
            {
                "kind": "as_safety_owner_evidence_reviewed_v1",
                "provenance": "ai_authored",
                "review_status": "owner_approved_for_exploration",
                "cases": labels,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path, paired, labels


def _protocol(tmp_path: Path, owner_path: Path, monkeypatch):
    """Create a fixture protocol whose digests match current test sources."""
    monkeypatch.setitem(verifier.SOURCES, "owner_labels_sha256", owner_path)
    payload = {
        "kind": "as_safety_owner_evidence_diagnostic_v1",
        "claim_scope": "already_exposed_ai_authored_oracle_diagnostic_only",
        "case_order": "RE01-RE11,V01-V10,V12,V14,V16",
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
        **{key: verifier.digest(path) for key, path in verifier.SOURCES.items()},
    }
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _success_rows(paired: list[tuple[dict, dict]], labels: list[dict], protocol_path: Path):
    """Construct a synthetic perfect journal without invoking a model."""
    rows = [
        {
            "event": "header",
            "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        }
    ]
    for (case, _span), label in zip(paired, labels, strict=True):
        relation = (
            "current" if case["id"] == "V04" else case["expected_relation"]["target_relation"]
        )
        if label["accepted_owner_spans"]:
            selected = label["accepted_owner_spans"][0]
            index = selected["clause_index"]
            mention = selected["mention"]
            start = split_clauses(case["user_message"])[index - 1].index(mention)
            end = start + len(mention)
        else:
            index = start = end = None
        rows.extend(
            [
                {"event": "begin", "case_id": case["id"]},
                {
                    "event": "end",
                    "case_id": case["id"],
                    "source_clause_index": index,
                    "source_start": start,
                    "source_end": end,
                    "link_kind": label["accepted_link_kinds"][0],
                    "source_relation": relation,
                    "route": verifier._route(relation, case["expected_relation"]["event_status"]),
                    "error_stage": None,
                    "error_type": None,
                    "http_status": None,
                    "finish_reason": "stop",
                    "latency_ms": 1.0,
                },
            ]
        )
    return rows


def _write_journal(path: Path, rows: list[dict]) -> None:
    """Write test rows without exposing real model output."""
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_unreviewed_owner_labels_rejected_before_any_model_call(tmp_path, monkeypatch):
    path, paired, _labels = _synthetic_labels(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["review_status"] = "ai_assisted_unreviewed"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    called = []
    monkeypatch.setattr(runner, "verify_container", lambda *_args: called.append(True))
    args = argparse.Namespace(
        output=tmp_path / "journal.jsonl",
        spans=runner.SOURCE_PATHS["spans_sha256"],
        owner_labels=path,
        protocol=tmp_path / "missing-protocol.json",
        model_path=tmp_path / "missing-model.gguf",
        policy=tmp_path / "missing-policy.json",
        container_name="unused",
    )
    with pytest.raises(ValueError, match="not reviewed"):
        runner.run(args)
    assert not called and not args.output.exists()
    assert len(paired) == 24


def test_protocol_requires_reviewed_label_file_in_commit(tmp_path, monkeypatch):
    """A matching hash alone does not authorize an uncommitted owner label file."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    for key in runner.SOURCE_PATHS:
        path = tmp_path / f"{key}.json"
        path.write_text(key, encoding="utf-8")
        monkeypatch.setitem(runner.SOURCE_PATHS, key, path)
    model_path = tmp_path / "model.gguf"
    model_path.write_bytes(b"test-model")
    protocol = {
        "kind": "as_safety_owner_evidence_diagnostic_v1",
        "claim_scope": "already_exposed_ai_authored_oracle_diagnostic_only",
        "case_order": "RE01-RE11,V01-V10,V12,V14,V16",
        "retry_policy": "no_retry_manual_audit_on_interruption",
        "endpoint": runner.ENDPOINT,
        "server_image_digest": runner.IMAGE,
        "max_tokens": 180,
        "local_runtime": {
            "host_port": 18081,
            "cpu_count": 2,
            "memory_bytes": 4 * 1024**3,
            "context_tokens": 4096,
            "threads": 2,
            "parallel_slots": 1,
        },
        "model_sha256": runner.digest(model_path),
        **{key: runner.digest(path) for key, path in runner.SOURCE_PATHS.items()},
    }
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")

    def fake_git(command, **_kwargs):
        if command[1] == "status":
            return SimpleNamespace(stdout="")
        relative = command[2].removeprefix("HEAD:")
        if relative == "owner_labels_sha256.json":
            return SimpleNamespace(stdout=b"different committed labels")
        return SimpleNamespace(stdout=(tmp_path / relative).read_bytes())

    monkeypatch.setattr(runner.subprocess, "run", fake_git)
    with pytest.raises(ValueError, match="owner_labels_sha256 is not committed"):
        runner.validate_protocol(
            protocol_path,
            model_path,
            runner.SOURCE_PATHS["policy_sha256"],
            runner.SOURCE_PATHS["spans_sha256"],
            runner.SOURCE_PATHS["owner_labels_sha256"],
        )


@pytest.mark.parametrize("change", ["missing", "wrong_order", "bad_span", "v04_kind"])
def test_reviewed_label_preflight_rejects_inconsistent_rows(tmp_path, change):
    path, paired, labels = _synthetic_labels(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if change == "missing":
        payload["cases"].pop()
    elif change == "wrong_order":
        payload["cases"][0], payload["cases"][1] = (payload["cases"][1], payload["cases"][0])
    elif change == "bad_span":
        payload["cases"][0]["accepted_owner_spans"][0]["mention"] = "없는 출처"
    else:
        payload["cases"][runner.ACTIVE_IDS.index("V04")]["accepted_link_kinds"] = ["explicit_other"]
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="owner"):
        runner.load_reviewed_owner_labels(path, paired)
    assert len(labels) == 24


def test_one_call_records_offsets_not_source_text(tmp_path, monkeypatch):
    _path, paired, labels = _synthetic_labels(tmp_path)
    case, span = paired[0]
    mention = labels[0]["accepted_owner_spans"][0]["mention"]
    index = labels[0]["accepted_owner_spans"][0]["clause_index"]
    calls = []

    def fake_post(_endpoint, _model_id, messages, _policy, schema):
        calls.append((messages, schema))
        return SimpleNamespace(
            content=json.dumps(
                {
                    "source_mention": mention,
                    "source_clause_index": index,
                    "link_kind": "same_entity",
                    "source_relation": "current",
                },
                ensure_ascii=False,
            ),
            finish_reason="stop",
        )

    monkeypatch.setattr(runner, "post_completion", fake_post)
    row = runner._call(case, span, object())
    assert len(calls) == 1
    assert row["source_clause_index"] == index
    assert row["source_relation"] == "current"
    assert row["error_stage"] is None
    serialized = json.dumps(row, ensure_ascii=False)
    assert mention not in serialized
    assert case["user_message"] not in serialized
    assert verifier._check_end(row, case) == (index, mention)


@pytest.mark.parametrize(
    ("response", "stage", "kind", "finish", "status"),
    [
        (
            SimpleNamespace(content="{", finish_reason="stop"),
            "contract",
            "JSONDecodeError",
            "stop",
            None,
        ),
        (
            SimpleNamespace(content='{"source_relation":"current"}', finish_reason="length"),
            "response",
            "ValueError",
            "length",
            None,
        ),
        (
            urllib.error.HTTPError("http://127.0.0.1/", 503, "private body", None, None),
            "response",
            "HTTPError",
            None,
            503,
        ),
    ],
)
def test_failure_keeps_one_call_and_no_raw_body(
    tmp_path, monkeypatch, response, stage, kind, finish, status
):
    _path, paired, _labels = _synthetic_labels(tmp_path)
    case, span = paired[0]
    calls = []

    def fake_post(*_args):
        calls.append(True)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(runner, "post_completion", fake_post)
    row = runner._call(case, span, object())
    assert len(calls) == 1
    assert row["error_stage"] == stage
    assert row["error_type"] == kind
    assert row["finish_reason"] == finish
    assert row["http_status"] == status
    assert row["source_relation"] is None
    assert "private body" not in json.dumps(row)
    assert verifier._check_end(row, case) == (None, None)


def test_full_journal_audit_scores_evidence_and_v04_overlay(tmp_path, monkeypatch):
    owner_path, paired, labels = _synthetic_labels(tmp_path)
    protocol_path = _protocol(tmp_path, owner_path, monkeypatch)
    rows = _success_rows(paired, labels, protocol_path)
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, rows)
    result = verifier.verify(protocol_path, journal_path)
    assert result["summary"]["all"]["denominator"] == 24
    assert result["summary"]["all"]["relation_correct"] == 24
    assert result["summary"]["all"]["source_span_correct"] == 24
    assert result["summary"]["all"]["link_kind_correct"] == 24
    assert result["summary"]["sensitivity_excluding_V03_V04"]["denominator"] == 22
    assert result["development_thresholds"]["met"] is True
    assert result["historical_comparison_allowed"] is False
    v04 = rows[2 + 2 * runner.ACTIVE_IDS.index("V04")]
    changed = copy.deepcopy(v04)
    changed["source_relation"] = "other"
    with pytest.raises(ValueError, match="successful owner evidence"):
        verifier._check_end(changed, paired[runner.ACTIVE_IDS.index("V04")][0])
    rows[2 + 2 * runner.ACTIVE_IDS.index("V04")]["link_kind"] = "explicit_other"
    rows[2 + 2 * runner.ACTIVE_IDS.index("V04")]["source_relation"] = "other"
    rows[2 + 2 * runner.ACTIVE_IDS.index("V04")]["route"] = "collecting_service_request"
    _write_journal(journal_path, rows)
    result = verifier.verify(protocol_path, journal_path)
    assert result["summary"]["all"]["relation_correct"] == 23
    assert result["summary"]["sensitivity_excluding_V03_V04"]["relation_correct"] == 22
    assert result["development_thresholds"]["met"] is True


@pytest.mark.parametrize("mutation", ["missing_end", "wrong_order", "raw_source", "bad_offset"])
def test_verifier_rejects_tampered_journal(tmp_path, monkeypatch, mutation):
    owner_path, paired, labels = _synthetic_labels(tmp_path)
    protocol_path = _protocol(tmp_path, owner_path, monkeypatch)
    rows = _success_rows(paired, labels, protocol_path)
    if mutation == "missing_end":
        rows.pop()
    elif mutation == "wrong_order":
        rows[1]["case_id"] = "RE02"
    elif mutation == "raw_source":
        rows[2]["source_mention"] = "private text"
    else:
        rows[2]["source_end"] = 9999
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, rows)
    with pytest.raises(ValueError):
        verifier.verify(protocol_path, journal_path)
