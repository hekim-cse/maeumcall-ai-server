"""Independent checks for the owner-resolution development protocol."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from scripts import verify_as_safety_owner_resolution_development as verifier
from scripts.probe_as_safety_clause_index import split_clauses


@pytest.fixture(autouse=True)
def _allow_synthetic_protocol(monkeypatch):
    monkeypatch.setattr(verifier, "_require_committed", lambda _path: None)


def _protocol() -> dict:
    return {
        "kind": "as_safety_owner_resolution_development_v1",
        "claim_scope": "already_exposed_ai_authored_a_only_development_only",
        "case_order": "RE01-RE06,RE08-RE11,V01-V08,V10,V12,V14,V16",
        "endpoint": "http://127.0.0.1:18081/v1/chat/completions",
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
        "server_image_digest": (
            "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
        ),
        "model_repo_revision": "a" * 40,
        "model_sha256": "b" * 64,
        "input_hashes": {key: verifier.digest(path) for key, path in verifier.INPUTS.items()},
        "source_manifest": {
            path: verifier.digest(verifier.ROOT / path)
            for path in verifier.expected_manifest_paths()
        },
    }


def _full_clause_span(case: dict) -> dict:
    clause = split_clauses(case["user_message"])[0]
    return {
        "clause_index": 1,
        "start": 0,
        "end": len(clause),
        "quote_sha256": hashlib.sha256(clause.encode("utf-8")).hexdigest(),
    }


def _journal(tmp_path):
    protocol_path = tmp_path / "protocol.json"
    raw = json.dumps(_protocol()).encode()
    protocol_path.write_bytes(raw)
    rows = [{"event": "header", "protocol_sha256": hashlib.sha256(raw).hexdigest()}]
    for case in verifier._reviewed_cases():
        span = _full_clause_span(case)
        relation = case["gold_relation"]
        rows.extend(
            [
                {"event": "begin", "case_id": case["id"]},
                {
                    "event": "end",
                    "case_id": case["id"],
                    "stage1": {
                        "called": True,
                        "status": "validated",
                        "spans": {
                            "event_span": span.copy(),
                            "subject_span": span.copy(),
                            "owner_span": span.copy(),
                        },
                        "owner_kind": "explicit",
                        "cue_spans": [span.copy()],
                        "distinct_cue_index": 0,
                        "finish_reason": "stop",
                        "latency_ms": 2.0,
                        "error": None,
                    },
                    "stage2": {
                        "called": True,
                        "status": "validated",
                        "skip_reason": None,
                        "model_relation": relation,
                        "effective_relation": relation,
                        "finish_reason": "stop",
                        "latency_ms": 2.0,
                        "error": None,
                    },
                    "source_relation": relation,
                    "route": (
                        "collecting_service_request"
                        if relation == "other"
                        else "safety_action_required"
                        if case["event_status"] == "observed"
                        else "confirming_safety_status"
                    ),
                    "total_latency_ms": 5.0,
                },
            ]
        )
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, rows)
    return protocol_path, journal_path, rows


def _write_journal(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_manifest_closure_includes_core_llm_and_prior_omissions():
    paths = verifier.expected_manifest_paths()
    assert {
        "core/__init__.py",
        "core/config.py",
        "core/observability.py",
        "llm/__init__.py",
        "llm/errors.py",
        "llm/huggingface_provider.py",
        "llm/structured_output.py",
        "scripts/probe_as_safety_grounded_entity_link_v1.py",
        "scripts/probe_as_safety_entity_link_v1.py",
        "scripts/run_as_safety_compact_relation_development.py",
        "scripts/run_as_safety_owner_resolution_development.py",
        "scripts/probe_as_safety_owner_resolution_v1.py",
        "scripts/verify_as_safety_owner_resolution_development.py",
    } <= paths
    assert all(path.endswith(".py") for path in paths)


def test_unlisted_dynamic_import_is_rejected(tmp_path, monkeypatch):
    source = tmp_path / "scripts" / "dynamic.py"
    source.parent.mkdir()
    source.write_text(
        "import importlib\nimportlib.import_module('scripts.foo')\n", encoding="utf-8"
    )
    monkeypatch.setattr(verifier, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="dynamic import"):
        verifier._imported_files(source)


def test_45_row_result_counts_calls_latency_and_gate(tmp_path):
    protocol_path, journal_path, _ = _journal(tmp_path)
    result = verifier.verify(protocol_path, journal_path)
    assert result["summary"]["all"]["denominator"] == 22
    assert result["summary"]["all"]["relation_correct"] == 22
    assert result["summary"]["all"]["calls"] == 44
    assert result["summary"]["all"]["stage2_skipped"] == 0
    assert result["summary"]["all"]["errors"] == 0
    assert result["latency_nearest_rank_ms"]["total"] == {"denominator": 22, "p50": 5.0, "p95": 5.0}
    assert result["development_thresholds"]["met"] is True
    assert result["raw_model_output_independently_reproducible"] is False
    assert result["quoted_relationship_semantics_independently_verified"] is False
    assert "user_message" not in json.dumps(result, ensure_ascii=False)


def test_missing_subject_skips_second_call_and_keeps_denominator(tmp_path):
    protocol_path, journal_path, rows = _journal(tmp_path)
    first, second = rows[2]["stage1"], rows[2]["stage2"]
    first["spans"]["subject_span"] = None
    second.update(
        {
            "called": False,
            "status": "skipped",
            "skip_reason": "missing_event_subject_owner",
            "model_relation": None,
            "effective_relation": None,
            "finish_reason": None,
            "latency_ms": None,
        }
    )
    rows[2]["source_relation"] = "unknown"
    rows[2]["route"] = "confirming_safety_status"
    rows[2]["total_latency_ms"] = 3.0
    _write_journal(journal_path, rows)
    result = verifier.verify(protocol_path, journal_path)
    assert result["summary"]["all"]["denominator"] == 22
    assert result["summary"]["all"]["calls"] == 43
    assert result["summary"]["all"]["stage2_skipped"] == 1
    assert result["summary"]["all"]["unknown_outputs"] == 1
    assert result["development_thresholds"]["met"] is False


def test_other_requires_explicit_distinct_cue(tmp_path):
    protocol_path, journal_path, rows = _journal(tmp_path)
    case = next(row for row in rows if row.get("event") == "end" and row["case_id"] == "RE09")
    case["stage1"]["distinct_cue_index"] = None
    case["stage2"]["effective_relation"] = "unknown"
    case["source_relation"] = "unknown"
    case["route"] = "confirming_safety_status"
    _write_journal(journal_path, rows)
    result = verifier.verify(protocol_path, journal_path)
    assert result["by_gold_relation"]["other"]["relation_correct"] == 5
    assert result["development_thresholds"]["met"] is False


@pytest.mark.parametrize("span_name", ["event_span", "subject_span", "owner_span", "cue_span"])
def test_each_synthetic_span_is_independent_and_hash_checked(tmp_path, span_name):
    protocol_path, journal_path, rows = _journal(tmp_path)
    stage1 = rows[2]["stage1"]
    spans = {**stage1["spans"], "cue_span": stage1["cue_spans"][0]}
    assert len({id(span) for span in spans.values()}) == 4
    original_hashes = {name: span["quote_sha256"] for name, span in spans.items()}
    spans[span_name]["quote_sha256"] = "0" * 64
    assert all(
        span["quote_sha256"] == original_hashes[name]
        for name, span in spans.items()
        if name != span_name
    )
    _write_journal(journal_path, rows)
    with pytest.raises(ValueError, match="source quote anchor differs"):
        verifier.verify(protocol_path, journal_path)


@pytest.mark.parametrize("mutation", ["offset", "hash", "missing_core_hash", "route", "retry"])
def test_anchor_manifest_route_and_retry_tampering_rejected(tmp_path, mutation):
    protocol_path, journal_path, rows = _journal(tmp_path)
    changed = copy.deepcopy(rows)
    if mutation == "offset":
        changed[2]["stage1"]["spans"]["subject_span"]["end"] -= 1
    elif mutation == "hash":
        changed[2]["stage1"]["spans"]["subject_span"]["quote_sha256"] = "0" * 64
    elif mutation == "route":
        changed[2]["route"] = "collecting_service_request"
    elif mutation == "retry":
        changed[3]["case_id"] = "RE01"
        changed[4]["case_id"] = "RE01"
    else:
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        protocol["source_manifest"].pop("core/config.py")
        protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    if mutation != "missing_core_hash":
        _write_journal(journal_path, changed)
    with pytest.raises(ValueError):
        verifier.verify(protocol_path, journal_path)


def test_stage_one_error_skips_stage_two_and_blocks_gate(tmp_path):
    protocol_path, journal_path, rows = _journal(tmp_path)
    first, second = rows[2]["stage1"], rows[2]["stage2"]
    first.update(
        {
            "status": "response_error",
            "spans": None,
            "owner_kind": None,
            "cue_spans": None,
            "distinct_cue_index": None,
            "finish_reason": None,
            "error": "response_error",
        }
    )
    second.update(
        {
            "called": False,
            "status": "skipped",
            "skip_reason": "stage1_invalid",
            "model_relation": None,
            "effective_relation": None,
            "finish_reason": None,
            "latency_ms": None,
        }
    )
    rows[2]["source_relation"] = "unknown"
    rows[2]["route"] = "confirming_safety_status"
    rows[2]["total_latency_ms"] = 3.0
    _write_journal(journal_path, rows)
    result = verifier.verify(protocol_path, journal_path)
    assert result["summary"]["all"]["errors"] == 1
    assert result["summary"]["all"]["calls"] == 43
    assert result["development_thresholds"]["met"] is False
