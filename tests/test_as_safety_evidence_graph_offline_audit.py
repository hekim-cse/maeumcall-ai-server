"""Posthoc-only counterfactuals keep original model output and scores intact."""

import json
import re
from collections import Counter
from hashlib import sha256
from pathlib import Path

import pytest

from experiments.as_safety_evidence_graph_v1.offline_audit import (
    _anchor_status,
    audit,
    audit_response,
)

MESSAGE = "접수할 프린터가 고장입니다. 옆 충전기에서 불꽃이 났어요."
EVENT = {"clause_index": 2, "quote": "불꽃이 났어요"}
SUBJECT = {"clause_index": 2, "quote": "옆 충전기"}
GRAPH = {
    "subject_span": SUBJECT,
    "event_subject_kind": "subject",
    "event_subject_evidence_span": {
        "clause_index": 2,
        "quote": "옆 충전기에서 불꽃이 났어요",
    },
    "target_edge_kind": "distinct",
    "target_edge_evidence_span": SUBJECT,
}


def _case():
    return {"user_message": MESSAGE}


def _event():
    return {"event_span": EVENT, "hazard_owner_span": SUBJECT, "owner_to_target": "other"}


def _label():
    return {
        "event_subject_kind": "subject",
        "event_subject_evidence_span": GRAPH["event_subject_evidence_span"],
        "target_edge_kind": "distinct",
        "target_edge_evidence_span": SUBJECT,
    }


def test_valid_response_is_scored_without_repair():
    result = audit_response(json.dumps(GRAPH), _case(), _event(), _label())
    assert set(result["anchor_status"].values()) == {"anchored"}
    assert result["event_cue_overlaps_event"] is True
    assert result["event_cue_overlaps_subject"] is True
    assert result["subject_raw_exact"] is True
    assert result["attachment_kind_correct"] is True
    assert result["edge_kind_correct"] is True
    assert result["repair_fields"] == []
    assert result["repair_contract_status"] == "validated"
    assert result["repair_relation_correct"] is True


def test_unique_wrong_clause_repair_changes_indices_only():
    graph = json.loads(json.dumps(GRAPH))
    for field in (
        "subject_span",
        "event_subject_evidence_span",
        "target_edge_evidence_span",
    ):
        graph[field]["clause_index"] = 1
    original = json.dumps(graph, ensure_ascii=False)
    result = audit_response(original, _case(), _event(), _label())
    assert result["repair_fields"] == sorted(
        ("subject_span", "event_subject_evidence_span", "target_edge_evidence_span")
    )
    assert result["subject_raw_exact"] is False
    assert result["repair_contract_status"] == "validated"
    assert result["repair_relation_correct"] is True
    assert json.loads(original) == graph  # repair never mutates the source object or bytes


def test_absent_quote_cannot_be_repaired():
    graph = {**GRAPH, "subject_span": {"clause_index": 2, "quote": "존재하지 않는 장치"}}
    result = audit_response(json.dumps(graph, ensure_ascii=False), _case(), _event(), _label())
    assert result["anchor_status"]["subject_span"] == "quote_absent"
    assert result["repair_fields"] == []
    assert result["repair_contract_status"] == "quote_unanchored"


def test_repeated_quote_in_other_clause_is_ambiguous():
    clauses = ("프린터입니다.", "충전기와 충전기가 있습니다.")
    assert _anchor_status({"clause_index": 1, "quote": "충전기"}, clauses, "subject_span") == (
        "wrong_clause_ambiguous",
        None,
        None,
    )


def test_kind_projection_is_separate_from_contract_and_gold():
    graph = {
        **GRAPH,
        "event_subject_kind": "location",
        "target_edge_kind": "part_of",
        "target_edge_evidence_span": {"clause_index": 1, "quote": "프린터"},
    }
    result = audit_response(json.dumps(graph, ensure_ascii=False), _case(), _event(), _label())
    assert result["repair_contract_status"] == "validated"
    assert result["kind_projection"] == "current"
    assert result["kind_projection_correct"] is False
    assert result["subject_raw_exact"] is True
    assert result["attachment_kind_correct"] is False
    assert result["edge_kind_correct"] is False


def test_first_contract_error_does_not_hide_later_span_error():
    graph = {
        **GRAPH,
        "event_subject_evidence_span": {"clause_index": 1, "quote": "프린터"},
        "target_edge_evidence_span": {"clause_index": 2, "quote": "원문에 없는 물체"},
    }
    result = audit_response(json.dumps(graph, ensure_ascii=False), _case(), _event(), _label())
    assert result["event_cue_overlaps_event"] is False
    assert result["anchor_status"]["target_edge_evidence_span"] == "quote_absent"
    assert result["repair_contract_status"] == "quote_unanchored"


@pytest.mark.parametrize(
    ("change", "expected_error", "expected_anchor"),
    [
        ({"event_subject_kind": "not_a_kind"}, "attachment_kind_invalid", "anchored"),
        ({"target_edge_kind": "not_an_edge"}, "edge_kind_invalid", "anchored"),
        (
            {"subject_span": {**SUBJECT, "unknown": "field"}},
            "quote_fields_invalid",
            "quote_fields_invalid",
        ),
        ({"subject_span": {"clause_index": 2, "quote": ""}}, "quote_blank", "quote_blank"),
        ({"subject_span": {"clause_index": 2, "quote": " "}}, "quote_blank", "quote_blank"),
        (
            {"subject_span": {"clause_index": 2, "quote": " 옆 충전기"}},
            "quote_blank",
            "quote_blank",
        ),
        (
            {"subject_span": {"clause_index": 2, "quote": "옆 충전기 "}},
            "quote_blank",
            "quote_blank",
        ),
    ],
)
def test_malformed_graph_fields_keep_finite_independent_error_codes(
    change, expected_error, expected_anchor
):
    result = audit_response(json.dumps({**GRAPH, **change}), _case(), _event(), _label())
    assert result["anchor_status"]["subject_span"] == expected_anchor
    assert result["repair_fields"] == []
    assert result["repair_contract_status"] == expected_error
    assert result["repair_relation_correct"] is False
    if "target_edge_kind" in change:
        assert result["kind_projection"] is None


def test_unknown_top_level_graph_field_is_rejected():
    raw = json.dumps({**GRAPH, "unknown": "field"})
    with pytest.raises(ValueError, match="raw graph shape differs"):
        audit_response(raw, _case(), _event(), _label())


def test_journal_tamper_fails_before_private_raw_access(tmp_path):
    data = Path("evals/structured_nlu/data/ai_heldout")
    journal = tmp_path / "journal.jsonl"
    journal.write_bytes(
        (data / "as-safety-evidence-graph-v1-development-journal.v1.jsonl").read_bytes() + b"\n"
    )
    with pytest.raises(ValueError, match="identity differs"):
        audit(
            data / "as-safety-evidence-graph-v1-development-protocol.v1.json",
            journal,
            data / "as-safety-evidence-graph-v1-development-verification.v1.json",
            tmp_path / "missing-private-raw",
        )


def test_frozen_private_raw_offline_audit_if_present():
    private = Path.home() / ".local/share/maeumcall-evaluations/as-safety-evidence-graph-v1/raw"
    if not private.is_dir():
        pytest.skip("private raw archive is intentionally outside the repository")
    data = Path("evals/structured_nlu/data/ai_heldout")
    result = audit(
        data / "as-safety-evidence-graph-v1-development-protocol.v1.json",
        data / "as-safety-evidence-graph-v1-development-journal.v1.jsonl",
        data / "as-safety-evidence-graph-v1-development-verification.v1.json",
        private,
    )
    assert result["raw_count"] == 19
    assert result["summary"]["original_contract_valid"] == 4
    assert result["summary"]["format_only_repair_attempted"] == 5
    assert result["summary"]["format_only_contract_valid"] == 7
    assert result["summary"]["format_only_relation_correct"] == 3
    assert result["summary"]["format_only_newly_valid"] == 3
    assert result["summary"]["format_only_newly_relation_correct"] == 0
    assert result["summary"]["kind_only_projection_correct"] == 9
    assert result["summary"]["raw_subject_exact_nonnull"] == 0
    assert result["summary"]["raw_subject_null_correct"] == 0
    assert all(ord(char) < 128 for char in json.dumps(result["events"], ensure_ascii=False))
    committed = json.loads(
        Path(
            "evals/structured_nlu/data/ai_heldout/as-safety-evidence-graph-v1-posthoc-error-audit.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert result["events"] == committed["events"]
    assert result["summary"] == committed["summary"]


def test_committed_posthoc_report_is_sanitized_and_internally_consistent():
    """Validate the portable report without relying on private raw in CI."""
    data = Path("evals/structured_nlu/data/ai_heldout")
    report = json.loads(
        (data / "as-safety-evidence-graph-v1-posthoc-error-audit.v1.json").read_text(
            encoding="utf-8"
        )
    )
    protocol = (data / "as-safety-evidence-graph-v1-development-protocol.v1.json").read_bytes()
    journal = (data / "as-safety-evidence-graph-v1-development-journal.v1.jsonl").read_bytes()
    verification = json.loads(
        (data / "as-safety-evidence-graph-v1-development-verification.v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert set(report) == {
        "kind",
        "claim_scope",
        "protocol_sha256",
        "journal_sha256",
        "source_verifier_sha256",
        "raw_count",
        "summary",
        "events",
    }
    assert report["kind"] == "as_safety_evidence_graph_v1_posthoc_error_audit"
    assert report["claim_scope"] == "exposed_development_set_posthoc_diagnostic_only"
    assert (
        report["protocol_sha256"] == verification["protocol_sha256"] == sha256(protocol).hexdigest()
    )
    assert report["journal_sha256"] == verification["journal_sha256"] == sha256(journal).hexdigest()
    assert (
        report["source_verifier_sha256"]
        == sha256(
            Path("experiments/as_safety_evidence_graph_v1/verify.py").read_bytes()
        ).hexdigest()
    )

    journal_rows = [json.loads(line) for line in journal.decode("utf-8").splitlines()]
    called_stages = [
        (row["case_id"], stage["event_index"], stage)
        for row in journal_rows
        if row.get("event") == "end"
        for stage in row["stages"]
        if stage["called"]
    ]
    events = report["events"]
    assert report["raw_count"] == len(events) == len(called_stages) == 19
    event_keys = {
        "case_id",
        "event_index",
        "raw_sha256",
        "gold_category",
        "original_status",
        "original_first_error",
        "anchor_status",
        "event_cue_overlaps_event",
        "event_cue_overlaps_subject",
        "subject_raw_exact",
        "gold_subject_present",
        "attachment_kind_correct",
        "edge_kind_correct",
        "attachment_evidence_raw_exact",
        "edge_evidence_raw_exact",
        "kind_projection",
        "kind_projection_correct",
        "repair_fields",
        "repair_contract_status",
        "repair_relation_correct",
    }
    span_fields = {
        "subject_span",
        "event_subject_evidence_span",
        "target_edge_evidence_span",
    }
    allowed_anchor = {
        "anchored",
        "null",
        "wrong_clause_unique",
        "wrong_clause_ambiguous",
        "quote_absent",
        "quote_nonunique",
        "quote_fields_invalid",
        "quote_index_invalid",
        "quote_type_invalid",
        "quote_blank",
    }
    allowed_errors = {
        "event_attachment_unlinked",
        "quote_unanchored",
        "subject_attachment_unlinked",
    }
    categories = {
        "observed_current",
        "observed_other",
        "observed_unknown",
        "uncertain_current",
    }
    for event, (case_id, index, stage) in zip(events, called_stages, strict=True):
        assert set(event) == event_keys
        assert (event["case_id"], event["event_index"]) == (case_id, index)
        assert re.fullmatch(r"ES\d{2}", case_id)
        assert event["raw_sha256"] == stage["raw_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", event["raw_sha256"])
        assert event["gold_category"] in categories
        assert event["original_status"] == stage["status"] in {"validated", "contract_error"}
        assert event["original_first_error"] == stage["error_code"]
        assert event["original_first_error"] in allowed_errors | {None}
        assert set(event["anchor_status"]) == span_fields
        assert set(event["anchor_status"].values()) <= allowed_anchor
        assert event["repair_contract_status"] in allowed_errors | {"validated"}
        assert type(event["repair_fields"]) is list
        assert len(event["repair_fields"]) == len(set(event["repair_fields"]))
        assert set(event["repair_fields"]) <= span_fields
        assert event["kind_projection"] in {"current", "other", "unknown", None}
        for key in event_keys - {
            "case_id",
            "event_index",
            "raw_sha256",
            "gold_category",
            "original_status",
            "original_first_error",
            "anchor_status",
            "kind_projection",
            "repair_fields",
            "repair_contract_status",
        }:
            assert type(event[key]) is bool or event[key] is None
        if event["repair_relation_correct"]:
            assert event["repair_contract_status"] == "validated"

    summary = report["summary"]
    assert set(summary) == {
        "original_contract_valid",
        "format_only_repair_attempted",
        "format_only_contract_valid",
        "format_only_relation_correct",
        "format_only_newly_valid",
        "format_only_newly_relation_correct",
        "kind_only_projection_correct",
        "gold_category_counts",
        "kind_only_projection_by_category",
        "raw_subject_exact_nonnull",
        "raw_subject_null_correct",
        "raw_attachment_kind_correct",
        "raw_edge_kind_correct",
        "raw_attachment_evidence_exact",
        "raw_edge_evidence_exact",
        "anchor_status_counts",
    }
    expected_counts = {
        "original_contract_valid": sum(e["original_status"] == "validated" for e in events),
        "format_only_repair_attempted": sum(bool(e["repair_fields"]) for e in events),
        "format_only_contract_valid": sum(
            e["repair_contract_status"] == "validated" for e in events
        ),
        "format_only_relation_correct": sum(e["repair_relation_correct"] for e in events),
        "format_only_newly_valid": sum(
            e["original_status"] != "validated" and e["repair_contract_status"] == "validated"
            for e in events
        ),
        "format_only_newly_relation_correct": sum(
            e["original_status"] != "validated" and e["repair_relation_correct"] for e in events
        ),
        "kind_only_projection_correct": sum(e["kind_projection_correct"] for e in events),
        "raw_subject_exact_nonnull": sum(
            e["subject_raw_exact"] and e["gold_subject_present"] for e in events
        ),
        "raw_subject_null_correct": sum(
            e["subject_raw_exact"] and not e["gold_subject_present"] for e in events
        ),
        "raw_attachment_kind_correct": sum(e["attachment_kind_correct"] for e in events),
        "raw_edge_kind_correct": sum(e["edge_kind_correct"] for e in events),
        "raw_attachment_evidence_exact": sum(e["attachment_evidence_raw_exact"] for e in events),
        "raw_edge_evidence_exact": sum(e["edge_evidence_raw_exact"] for e in events),
    }
    for key, expected in expected_counts.items():
        assert type(summary[key]) is int and summary[key] == expected
    assert summary["gold_category_counts"] == dict(Counter(e["gold_category"] for e in events))
    assert set(summary["gold_category_counts"]) == categories
    assert summary["kind_only_projection_by_category"] == {
        category: sum(
            e["kind_projection_correct"] for e in events if e["gold_category"] == category
        )
        for category in categories
    }
    assert set(summary["anchor_status_counts"]) == span_fields
    for field in span_fields:
        assert summary["anchor_status_counts"][field] == dict(
            Counter(e["anchor_status"][field] for e in events)
        )
        assert sum(summary["anchor_status_counts"][field].values()) == len(events)

    # All string values are identifiers, finite codes, or hashes. This portable
    # artifact must not include user utterances, prompts, raw quotes or paths.
    forbidden_keys = {"quote", "user_message", "prompt", "raw_response", "path", "private_dir"}

    def check_privacy(value):
        if type(value) is dict:
            assert not (set(value) & forbidden_keys)
            for child in value.values():
                check_privacy(child)
        elif type(value) is list:
            for child in value:
                check_privacy(child)
        elif type(value) is str:
            assert value.isascii()
            assert "/" not in value and "\\" not in value
            assert not any(char.isspace() for char in value)

    check_privacy(report)
