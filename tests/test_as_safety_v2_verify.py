"""Tamper tests for the independent, development-only journal verifier."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from experiments.as_safety_v2 import verify as audit
from experiments.as_safety_v2 import verify_journal as journal
from experiments.as_safety_v2 import verify_sources as source


def _case() -> dict:
    message = "접수할 전기포트가 고장났습니다. 토스터에서 불꽃이 났습니다."
    clauses = source._clauses(message)
    return {
        "id": "V02",
        "message": message,
        "clauses": clauses,
        "relation": "other",
        "event_status": "observed",
        "references": {
            "event_reference": source._reference({"clause_index": 2, "quote": "불꽃"}, clauses),
            "subject_reference": source._reference({"clause_index": 2, "quote": "토스터"}, clauses),
            "owner_reference": source._reference({"clause_index": 2, "quote": "토스터"}, clauses),
        },
    }


def _valid_row(case: dict, private_dir) -> dict:
    raw1 = json.dumps(
        {
            "event_span": {"clause_index": 2, "quote": "불꽃"},
            "subject_span": {"clause_index": 2, "quote": "토스터"},
            "owner_span": {"clause_index": 2, "quote": "토스터"},
            "owner_kind": "explicit",
        },
        ensure_ascii=False,
    )
    raw2 = json.dumps(
        {
            "source_relation": "other",
            "distinct_evidence_span": {"clause_index": 2, "quote": "토스터"},
        },
        ensure_ascii=False,
    )
    for number, raw in ((1, raw1), (2, raw2)):
        (private_dir / f"V02-stage{number}.json.txt").write_text(raw, encoding="utf-8")
    clauses = case["clauses"]
    return {
        "event": "end",
        "case_id": "V02",
        "stage1": {
            "called": True,
            "status": "validated",
            "error_code": None,
            "error_field": None,
            "finish_reason": "stop",
            "latency_ms": 10.0,
            "raw_sha256": source.digest(raw1.encode()),
            "raw_bytes": len(raw1.encode()),
            "spans": {
                "event_span": source._reference({"clause_index": 2, "quote": "불꽃"}, clauses),
                "subject_span": source._reference({"clause_index": 2, "quote": "토스터"}, clauses),
                "owner_span": source._reference({"clause_index": 2, "quote": "토스터"}, clauses),
            },
            "owner_kind": "explicit",
        },
        "stage2": {
            "called": True,
            "status": "validated",
            "skip_reason": None,
            "error_code": None,
            "error_field": None,
            "finish_reason": "stop",
            "latency_ms": 11.0,
            "raw_sha256": source.digest(raw2.encode()),
            "raw_bytes": len(raw2.encode()),
            "model_relation": "other",
            "effective_relation": "other",
            "distinct_evidence_span": source._reference(
                {"clause_index": 2, "quote": "토스터"}, clauses
            ),
        },
        "source_relation": "other",
        "route": "collecting_service_request",
        "total_latency_ms": 22.0,
    }


def test_valid_private_raw_and_reference_are_independent(tmp_path):
    case = _case()
    result = audit.check_end(_valid_row(case, tmp_path), case, tmp_path)
    assert result["predicted_relation"] == "other"
    assert result["reference_matches"] == {"event": True, "subject": True, "owner": True}


@pytest.mark.parametrize(
    "mutation",
    [
        lambda row: row["stage1"]["spans"]["event_span"].update(start=1),
        lambda row: row["stage1"]["spans"]["subject_span"].update(quote_sha256="0" * 64),
        lambda row: row["stage1"].update(raw_bytes=2),
        lambda row: row["stage2"].update(effective_relation="current"),
        lambda row: row.update(route="safety_action_required"),
        lambda row: row["stage2"].update(called=False),
    ],
)
def test_tampered_rows_fail(tmp_path, mutation):
    case = _case()
    row = _valid_row(case, tmp_path)
    mutation(row)
    with pytest.raises(ValueError):
        audit.check_end(row, case, tmp_path)


def test_missing_evidence_must_skip_stage2(tmp_path):
    case = _case()
    row = _valid_row(case, tmp_path)
    row["stage1"]["spans"]["owner_span"] = None
    row["stage1"]["owner_kind"] = "unresolved"
    with pytest.raises(ValueError, match="stage2 call transition"):
        audit.check_end(row, case)


def test_implicit_owner_cannot_become_effective_other(tmp_path):
    case = _case()
    row = _valid_row(case, tmp_path)
    row["stage1"]["owner_kind"] = "implicit_coreference"
    with pytest.raises(ValueError, match="effective relation"):
        audit.check_end(row, case)


def test_repeated_span_cannot_select_second_occurrence():
    clauses = ("토스터 토스터",)
    second = {
        "clause_index": 1,
        "start": 4,
        "end": 7,
        "quote_sha256": source.digest("토스터".encode()),
    }
    with pytest.raises(ValueError, match="unique"):
        source._span(second, clauses)


def test_summary_rejects_partial_or_duplicated_denominator():
    row = {"id": "RE01"}
    with pytest.raises(ValueError, match="case order"):
        audit.summarize([deepcopy(row)] * 22)
    with pytest.raises(ValueError, match="case order"):
        audit.summarize([])


def test_private_raw_decision_cannot_disagree_with_journal(tmp_path):
    case = _case()
    row = _valid_row(case, tmp_path)
    row["stage2"]["model_relation"] = "unknown"
    row["stage2"]["effective_relation"] = "unknown"
    row["stage2"]["distinct_evidence_span"] = None
    row["source_relation"] = "unknown"
    row["route"] = "confirming_safety_status"
    with pytest.raises(ValueError, match="raw decision"):
        audit.check_end(row, case, tmp_path)


def test_response_error_requires_consistent_raw_state():
    stage = {
        "error_code": "network_error",
        "error_field": None,
        "finish_reason": None,
        "raw_sha256": None,
    }
    journal._response_error(stage)
    stage["raw_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="transport failure"):
        journal._response_error(stage)
    stage.update(error_code="finish_length", finish_reason="length")
    journal._response_error(stage)


def test_current_reviewed_inputs_reconstruct_22_cases():
    frozen = {key: (source.ROOT / path).read_bytes() for key, path in source.INPUTS.items()}
    cases = source._cases(frozen)
    assert tuple(case["id"] for case in cases) == source.CASE_IDS
    assert sum(case["relation"] == "current" for case in cases) == 16


def test_all_executing_sources_must_match_frozen_manifest(tmp_path):
    source_file = tmp_path / "experiments/as_safety_v2/verify_journal.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"frozen")
    manifest = {"experiments/as_safety_v2/verify_journal.py": source.digest(b"frozen")}
    audit._check_current_sources(manifest, root=tmp_path)
    source_file.write_bytes(b"modified")
    with pytest.raises(ValueError, match="executing source differs"):
        audit._check_current_sources(manifest, root=tmp_path)
