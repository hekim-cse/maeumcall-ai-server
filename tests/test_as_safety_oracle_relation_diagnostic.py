"""Check frozen oracle inputs, bounded calls, and independent journal audit."""

from __future__ import annotations

import copy
import hashlib
import json
import urllib.error
from types import SimpleNamespace

import pytest

from scripts import run_as_safety_oracle_relation_diagnostic as runner
from scripts import verify_as_safety_oracle_relation_diagnostic as verifier
from scripts.probe_as_safety_clause_index import split_clauses


def _reviewed_spans(tmp_path):
    cases = [
        case
        for key in ("re_dataset_sha256", "v_dataset_sha256")
        for case in json.loads(runner.SOURCE_PATHS[key].read_text(encoding="utf-8"))["cases"]
        if case["expected_relation"]["event_status"] != "nonoccurring"
    ]
    spans = []
    for case in cases:
        clauses = split_clauses(case["user_message"])
        gold = case["expected_relation"]
        spans.append(
            {
                "id": case["id"],
                "target_mention": "토스터"
                if case["id"] == "V04"
                else clauses[gold["product_index"] - 1],
                "hazard_event_mention": clauses[gold["hazard_index"] - 1],
            }
        )
        if case["id"] == "V04":
            spans[-1]["reviewed_interpretation"] = {
                "version": "v2_target_review",
                "target_relation": "current",
                "expected_route": "safety_action_required",
            }
    path = tmp_path / "reviewed-spans.json"
    path.write_text(
        json.dumps(
            {"kind": "as_safety_oracle_relation_spans_reviewed_v1", "cases": spans},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path, cases, spans


def test_only_24_active_cases_are_loaded_and_spans_are_unique(tmp_path, monkeypatch):
    path, _cases, _spans = _reviewed_spans(tmp_path)
    paired = runner.load_active_cases(path)
    assert len(paired) == 24
    assert tuple(case["id"] for case, _span in paired) == runner.ACTIVE_IDS
    assert "RE12" not in runner.ACTIVE_IDS
    assert "V11" not in runner.ACTIVE_IDS
    monkeypatch.setitem(verifier.SOURCES, "spans_sha256", path)
    assert verifier._check_spans([case for case, _span in paired]) == {
        "V04": {
            "version": "v2_target_review",
            "target_relation": "current",
            "expected_route": "safety_action_required",
        }
    }


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "wrong_clause"])
def test_span_preflight_rejects_unreviewed_or_ambiguous_anchor(tmp_path, mutation):
    path, cases, spans = _reviewed_spans(tmp_path)
    if mutation == "missing":
        spans[0]["target_mention"] = "존재하지 않는 대상"
    elif mutation == "duplicate":
        spans[1]["target_mention"] = "기"
    else:
        clauses = split_clauses(cases[0]["user_message"])
        spans[0]["target_mention"] = clauses[cases[0]["expected_relation"]["hazard_index"] - 1]
    path.write_text(
        json.dumps(
            {"kind": "as_safety_oracle_relation_spans_reviewed_v1", "cases": spans},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="mention"):
        runner.load_active_cases(path)


def test_v04_requires_explicit_reviewed_target_and_interpretation(tmp_path, monkeypatch):
    path, cases, spans = _reviewed_spans(tmp_path)
    v04 = next(span for span in spans if span["id"] == "V04")
    v04["target_mention"] = "전기포트"
    path.write_text(
        json.dumps(
            {"kind": "as_safety_oracle_relation_spans_reviewed_v1", "cases": spans},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setitem(verifier.SOURCES, "spans_sha256", path)
    with pytest.raises(ValueError, match="V04 reviewed interpretation"):
        runner.load_active_cases(path)
    with pytest.raises(ValueError, match="V04 reviewed interpretation"):
        verifier._check_spans(cases)


def test_single_oracle_call_records_only_finite_decision(monkeypatch, tmp_path):
    path, _cases, _spans = _reviewed_spans(tmp_path)
    case, span = runner.load_active_cases(path)[0]
    calls = []

    def fake_post(_endpoint, _model, messages, _policy, _schema):
        calls.append(messages)
        return SimpleNamespace(content='{"source_relation":"current"}', finish_reason="stop")

    monkeypatch.setattr(runner, "post_completion", fake_post)
    row = runner._call(case, span, object())
    assert len(calls) == 1
    assert row["source_relation"] == "current"
    assert row["route"] == "safety_action_required"
    assert row["error_stage"] is None
    assert case["user_message"] not in json.dumps(row, ensure_ascii=False)
    assert span["target_mention"] not in json.dumps(row, ensure_ascii=False)
    verifier._check_end(row, case)


@pytest.mark.parametrize(
    ("response", "expected_stage", "expected_type", "expected_finish", "expected_status"),
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
def test_failed_oracle_call_records_no_response_body(
    monkeypatch, tmp_path, response, expected_stage, expected_type, expected_finish, expected_status
):
    path, _cases, _spans = _reviewed_spans(tmp_path)
    case, span = runner.load_active_cases(path)[0]
    calls = 0

    def fake_post(*_args):
        nonlocal calls
        calls += 1
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(runner, "post_completion", fake_post)
    row = runner._call(case, span, object())
    assert calls == 1
    assert row["source_relation"] is None and row["route"] is None
    assert row["error_stage"] == expected_stage
    assert row["error_type"] == expected_type
    assert row["finish_reason"] == expected_finish
    assert row["http_status"] == expected_status
    assert "private body" not in json.dumps(row)
    verifier._check_end(row, case)


def test_independent_verifier_rejects_tampered_relation_or_status(monkeypatch, tmp_path):
    path, _cases, _spans = _reviewed_spans(tmp_path)
    case, span = runner.load_active_cases(path)[0]
    monkeypatch.setattr(
        runner,
        "post_completion",
        lambda *_args: SimpleNamespace(
            content='{"source_relation":"current"}', finish_reason="stop"
        ),
    )
    row = runner._call(case, span, object())
    changed = copy.deepcopy(row)
    changed["route"] = "collecting_service_request"
    with pytest.raises(ValueError, match="successful relation"):
        verifier._check_end(changed, case)
    changed = copy.deepcopy(row)
    changed["http_status"] = 503
    with pytest.raises(ValueError, match="successful relation"):
        verifier._check_end(changed, case)


def test_full_journal_verifies_v04_interpretation_and_row_order(monkeypatch, tmp_path):
    spans_path, _cases, _spans = _reviewed_spans(tmp_path)
    monkeypatch.setitem(verifier.SOURCES, "spans_sha256", spans_path)
    protocol = {
        "kind": "as_safety_oracle_relation_diagnostic_v1",
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
    protocol_path = tmp_path / "protocol.json"
    protocol_bytes = json.dumps(protocol, ensure_ascii=False).encode()
    protocol_path.write_bytes(protocol_bytes)
    rows = [{"event": "header", "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest()}]
    for case in verifier._active_cases():
        relation = (
            "current" if case["id"] == "V04" else case["expected_relation"]["target_relation"]
        )
        rows.extend(
            [
                {"event": "begin", "case_id": case["id"]},
                {
                    "event": "end",
                    "case_id": case["id"],
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
    journal_path = tmp_path / "journal.jsonl"
    journal_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    result = verifier.verify(protocol_path, journal_path)
    assert result["summary"]["all"]["denominator"] == 24
    assert result["summary"]["all"]["relation_correct"] == 24
    assert result["summary"]["all"]["gold_relation_counts"] == {
        "current": 16,
        "other": 6,
        "unknown": 2,
    }
    sensitivity = result["summary"]["sensitivity_excluding_V03_V04"]
    assert sensitivity == {
        "denominator": 22,
        "relation_correct": 22,
        "route_correct": 22,
        "errors": 0,
        "gold_relation_counts": {"current": 14, "other": 6, "unknown": 2},
    }
    assert result["by_gold_relation"] == {
        "current": {
            "denominator": 16,
            "correct": 16,
            "errors": 0,
            "contract_errors": 0,
            "http_errors": 0,
        },
        "other": {
            "denominator": 6,
            "correct": 6,
            "errors": 0,
            "contract_errors": 0,
            "http_errors": 0,
        },
        "unknown": {
            "denominator": 2,
            "correct": 2,
            "errors": 0,
            "contract_errors": 0,
            "http_errors": 0,
        },
    }
    assert [pair["case_ids"] for pair in result["contrast_pairs"]] == [
        ["V01", "V02"],
        ["V05", "V06"],
        ["V07", "V08"],
    ]
    assert all(
        pair["prediction_flipped"] and pair["expected_flip_recovered"]
        for pair in result["contrast_pairs"]
    )
    assert result["development_thresholds"]["met"] is True
    assert result["historical_comparison_allowed"] is False
    v04_end = rows[2 + 2 * runner.ACTIVE_IDS.index("V04")]
    v04_end["source_relation"] = "other"
    v04_end["route"] = "collecting_service_request"
    journal_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    changed_result = verifier.verify(protocol_path, journal_path)
    assert changed_result["summary"]["all"]["relation_correct"] == 23
    assert changed_result["summary"]["sensitivity_excluding_V03_V04"] == sensitivity
    assert changed_result["development_thresholds"]["met"] is True
    v04_end["source_relation"] = "current"
    v04_end["route"] = "safety_action_required"
    v02_end = rows[2 + 2 * runner.ACTIVE_IDS.index("V02")]
    v02_end["source_relation"] = "current"
    v02_end["route"] = "safety_action_required"
    journal_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    pair_failure = verifier.verify(protocol_path, journal_path)
    assert pair_failure["by_gold_relation"]["other"]["correct"] == 5
    assert pair_failure["contrast_pairs"][0]["predicted_relations"] == ["current", "current"]
    assert pair_failure["contrast_pairs"][0]["prediction_flipped"] is False
    assert pair_failure["contrast_pairs"][0]["expected_flip_recovered"] is False
    assert pair_failure["development_thresholds"]["met"] is False
    v02_end.update(
        {
            "source_relation": None,
            "route": None,
            "error_stage": "contract",
            "error_type": "ValueError",
            "http_status": None,
            "finish_reason": "stop",
        }
    )
    journal_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    contract_failure = verifier.verify(protocol_path, journal_path)
    assert contract_failure["by_gold_relation"]["other"]["errors"] == 1
    assert contract_failure["by_gold_relation"]["other"]["contract_errors"] == 1
    assert contract_failure["by_gold_relation"]["other"]["http_errors"] == 0
    v02_end.update(
        {
            "error_stage": "response",
            "error_type": "HTTPError",
            "http_status": 503,
            "finish_reason": None,
        }
    )
    journal_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    http_failure = verifier.verify(protocol_path, journal_path)
    assert http_failure["by_gold_relation"]["other"]["errors"] == 1
    assert http_failure["by_gold_relation"]["other"]["contract_errors"] == 0
    assert http_failure["by_gold_relation"]["other"]["http_errors"] == 1
    rows[1], rows[3] = rows[3], rows[1]
    journal_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="call order"):
        verifier.verify(protocol_path, journal_path)
