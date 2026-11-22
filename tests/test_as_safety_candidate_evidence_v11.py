"""Protect the source-only boundary of the offline candidate audit."""

import copy

import pytest
from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v10 import probe
from experiments.as_safety_atomic_edges_v11.audit import audit
from experiments.as_safety_atomic_edges_v11.evidence_view import annotate_candidates


def test_annotations_do_not_depend_on_owner_gold():
    case = probe.cases()["PC01"]
    changed = copy.deepcopy(case)
    changed["gold_subject_span"] = None
    changed["gold_kind"] = "unresolved"
    kiwi = Kiwi()
    assert annotate_candidates(case["user_message"], case["event_span"], kiwi) == (
        annotate_candidates(changed["user_message"], changed["event_span"], kiwi)
    )


def test_overlap_inventory_keeps_positive_gold_and_exposes_negative_distractors():
    result = audit()
    pc, nc = result["exposed_control_rows"]
    assert pc["gold_present_before_event"] is True
    assert pc["candidate_ids_by_position"]["crosses_event"] == ["P016", "P020"]
    assert nc["candidate_ids_by_position"]["inside_event"] == ["P008", "P020"]
    assert nc["candidate_ids_by_position"]["other_clause"] == ["P002", "P011"]
    assert result["previous_26_case_nominal_filter"]["nominal_chunk_gold_loss_ids"] == [
        "RE09",
        "RE10",
    ]
    assert result["owner_or_abstention_inferred"] is False


def test_ambiguous_event_mention_is_rejected():
    with pytest.raises(ValueError, match="unique and anchored"):
        annotate_candidates(
            "연기가 나고 연기가 났습니다.", {"clause_index": 1, "quote": "연기"}, Kiwi()
        )
