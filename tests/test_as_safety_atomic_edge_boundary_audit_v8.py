"""Offline source-span availability, without treating it as model accuracy."""

import hashlib
import inspect
import json

import pytest
from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v8 import boundary_audit as audit
from experiments.as_safety_v2.quotes import split_clauses


def _control_message(case_id: str) -> str:
    payload = json.loads(audit.SOURCES["PC_NC"].read_text())
    return next(item["user_message"] for item in payload["cases"] if item["case_id"] == case_id)


def test_positive_boundary_keeps_gold_and_removes_two_observed_overquotes():
    views = audit.candidate_views(_control_message("PC01"), Kiwi())
    assert [len(views[name]) for name in audit.FILTERS] == [22, 7, 5]
    for name in ("nominal_end", "nominal_chunk"):
        ids = {item.id for item in views[name]}
        assert "P014" in ids
        assert {"P013", "P022"}.isdisjoint(ids)
    # Noun-ending alone leaves two longer spans crossing the source particle.
    assert {"P016", "P020"}.issubset({item.id for item in views["nominal_end"]})
    assert {"P016", "P020"}.isdisjoint({item.id for item in views["nominal_chunk"]})
    # Shorter competing nouns remain; this filter cannot select the owner.
    assert {"P005", "P007"}.issubset({item.id for item in views["nominal_chunk"]})


def test_negative_control_still_has_candidates_and_cannot_prove_abstention():
    views = audit.candidate_views(_control_message("NC01"), Kiwi())
    assert [len(views[name]) for name in audit.FILTERS] == [35, 4, 3]
    assert all(views[name] for name in audit.FILTERS)


def test_filter_preserves_original_ids_offsets_and_exact_source_quotes():
    message = _control_message("PC01")
    clauses = split_clauses(message)
    views = audit.candidate_views(message, Kiwi())
    baseline = set(views["baseline"])
    for name in ("nominal_end", "nominal_chunk"):
        assert set(views[name]).issubset(baseline)
        for item in views[name]:
            assert clauses[item.clause_index - 1][item.start : item.end] == item.quote
            assert item.quote_sha256 == hashlib.sha256(item.quote.encode("utf-8")).hexdigest()


def test_generation_api_accepts_only_source_and_analyzer_not_gold():
    assert set(inspect.signature(audit.candidate_views).parameters) == {"message", "kiwi"}
    message = _control_message("PC01")
    original = {"message": message, "gold": "선풍기 모터"}
    changed = {**original, "gold": "연기"}
    assert audit.candidate_views(original["message"], Kiwi()) == audit.candidate_views(
        changed["message"], Kiwi()
    )


def test_offline_audit_reports_source_hashes_coverage_and_strict_losses():
    result = audit.audit()
    assert result["model_called"] is False
    assert result["owner_selection_or_abstention_evaluated"] is False
    assert result["source_sha256_by_group"] == audit.SOURCE_SHA256
    assert result["reviewed_owner_sha256"] == audit.LABEL_SHA256
    summary = result["summary"]
    assert (summary["case_count"], summary["positive_case_count"], summary["null_case_count"]) == (
        26,
        23,
        3,
    )
    assert summary["candidate_count_by_filter"] == {
        "baseline": 1570,
        "nominal_end": 525,
        "nominal_chunk": 239,
    }
    assert summary["positive_gold_covered_by_filter"] == {
        "baseline": 23,
        "nominal_end": 23,
        "nominal_chunk": 21,
    }
    assert summary["additional_gold_loss_vs_baseline_by_filter"] == {
        "baseline": 0,
        "nominal_end": 0,
        "nominal_chunk": 2,
    }
    assert summary["additional_gold_loss_case_ids_by_filter"]["nominal_chunk"] == [
        "RE09",
        "RE10",
    ]
    assert {row["case_id"] for row in result["cases"] if not row["gold_required"]} == {
        "NC01",
        "RE07",
        "V09",
    }
    rows = {row["case_id"]: row for row in result["cases"]}
    assert rows["PC01"]["gold_candidate_ids_by_filter"] == {
        "baseline": ["P014"],
        "nominal_end": ["P014"],
        "nominal_chunk": ["P014"],
    }
    assert rows["NC01"]["gold_candidate_ids_by_filter"] == {name: None for name in audit.FILTERS}
    for case_id in ("RE09", "RE10"):
        ids = rows[case_id]["gold_candidate_ids_by_filter"]
        assert len(ids["baseline"]) == len(ids["nominal_end"]) == 1
        assert ids["baseline"] == ids["nominal_end"]
        assert ids["nominal_chunk"] == []
        assert rows[case_id]["additional_gold_loss_vs_baseline_by_filter"]["nominal_chunk"] == 1
    assert len({row["case_id"] for row in result["cases"]}) == 26


def test_input_digest_mismatch_fails_closed(monkeypatch):
    monkeypatch.setitem(audit.SOURCE_SHA256, "PC_NC", "0" * 64)
    with pytest.raises(ValueError, match="development source digest differs"):
        audit.audit()


def test_only_allowed_exposed_development_sources_are_read():
    names = {path.name for path in (*audit.SOURCES.values(), audit.LABELS)}
    assert names == {
        "as-safety-eb-controls-v5-cases.json",
        "as-safety-relation-fresh-reviewed.v1.json",
        "as-safety-relation-v2-fresh-reviewed.v1.json",
        "as-safety-owner-evidence-reviewed.v1.json",
    }
