"""Verify surface recovery and the unchanged source constraints."""

import json

import pytest

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_atomic_edges_v12.run import _kiwi
from experiments.as_safety_contextual_part_evaluation import DATA
from experiments.as_safety_device_part import composed_source, surface_nominal_source
from experiments.as_safety_explicit_source import DirectSource
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate


def test_cp07_recovery_preserves_the_original_offsets():
    fixture = json.loads(DATA.read_bytes())
    case = next(item for item in fixture["cases"] if item["id"] == "CP07")
    candidate = next(item for item in case["candidates"] if item["id"] == "CP07-2")
    clauses = split_clauses(case["utterance"])
    span = anchor_span(candidate["span"], clauses, field="candidate")
    event = anchor_span(case["event"], clauses, field="event")
    pair = FixedPair(case["utterance"], clauses, event, SourceCandidate(candidate["id"], **span))
    assert composed_source(pair, "observed", _kiwi()) is None
    assert surface_nominal_source(pair, "observed", _kiwi()) == DirectSource(1, 0, 7, 10, 18)


@pytest.mark.parametrize(
    ("clause", "quote", "event", "following", "occurrence"),
    [
        (
            "인쇄기 집진판 옆 작업대에서 연기가 났습니다.",
            "인쇄기 집진판 옆 작업대",
            "연기가 났습니다",
            "",
            "observed",
        ),
        (
            "인쇄기 집진판 옆에서 연기가 났습니다.",
            "인쇄기 집진판",
            "연기가 났습니다",
            "",
            "observed",
        ),
        (
            "인쇄기 집진판에서 연기가 보였습니다.",
            "인쇄기 집진판",
            "연기가 보였습니다",
            "",
            "observed",
        ),
        (
            "인쇄기 집진판에서 연기가 났습니다.",
            "인쇄기 집진판",
            "연기가 났습니다",
            " 연기의 출처는 모르겠습니다.",
            "observed",
        ),
        ("인쇄기 집진판에서 연기가 났습니다.", "인쇄기 집진판", "연기가 났습니다", "", "uncertain"),
        ("인쇄기집진판에서 연기가 났습니다.", "인쇄기집진판", "연기가 났습니다", "", "observed"),
    ],
)
def test_surface_evidence_does_not_relax_other_guards(clause, quote, event, following, occurrence):
    text = clause + following
    clauses = split_clauses(text)
    anchor = anchor_span({"clause_index": 1, "quote": event}, clauses, field="event")
    span = anchor_span({"clause_index": 1, "quote": quote}, clauses, field="candidate")
    pair = FixedPair(text, clauses, anchor, SourceCandidate("test", **span))
    assert surface_nominal_source(pair, occurrence, _kiwi()) is None
