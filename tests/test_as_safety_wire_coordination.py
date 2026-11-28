"""Check independent source rule changes with synthetic quote anchors."""

import pytest

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_atomic_edges_v12.run import _kiwi
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate
from experiments.as_safety_wire_coordination import DETECTORS

SIMPLE = "방금 제습기 신호선에서 불꽃이 튀었습니다."
MULTIPLE = "어제 다른 기기의 충전기에서 불꽃이 튀었고, 오늘은 냉각 장치 포트에서 연기가 나왔습니다."
CHANGE = "냉각 장치 단자에서 연기가 났고, 건조기 옆면이 뜨거워지며 커버가 녹았습니다."
WIRE = ("wire_only", "combined")
COORDINATION = ("coordination_only", "combined")


@pytest.mark.parametrize(
    ("source", "event", "candidate", "expected"),
    [
        (SIMPLE, "불꽃이 튀었습니다", "제습기 신호선", WIRE),
        (SIMPLE, "불꽃이 튀었습니다", "신호선", ()),
        (
            "제습기 신호선 보관함에서 불꽃이 튀었습니다.",
            "불꽃이 튀었습니다",
            "제습기 신호선 보관함",
            (),
        ),
        (
            SIMPLE + " 제습기 신호선은 보관 구역 이름입니다.",
            "불꽃이 튀었습니다",
            "제습기 신호선",
            (),
        ),
        (MULTIPLE, "불꽃이 튀었고", "다른 기기의 충전기", COORDINATION),
        (MULTIPLE, "불꽃이 튀었고", "냉각 장치 포트", ()),
        (MULTIPLE, "연기가 나왔습니다", "냉각 장치 포트", COORDINATION),
        (CHANGE, "연기가 났고", "냉각 장치 단자", COORDINATION),
        (CHANGE, "건조기 옆면이 뜨거워지며 커버가 녹았습니다", "건조기 옆면", COORDINATION),
        (CHANGE, "건조기 옆면이 뜨거워지며 커버가 녹았습니다", "냉각 장치 단자", ()),
        (
            "제습기 신호선에서 불꽃이 튀었고, 냉각 장치 포트에서 연기가 나왔습니다.",
            "불꽃이 튀었고",
            "제습기 신호선",
            ("combined",),
        ),
        (
            MULTIPLE.removesuffix(".") + "만 처음 불꽃의 출처는 모르겠습니다.",
            "불꽃이 튀었고",
            "다른 기기의 충전기",
            (),
        ),
    ],
)
def test_independent_wire_and_coordination(source, event, candidate, expected):
    clauses = split_clauses(source)
    e = anchor_span({"clause_index": 1, "quote": event}, clauses, field="event")
    b = anchor_span({"clause_index": 1, "quote": candidate}, clauses, field="source")
    pair = FixedPair(source, clauses, e, SourceCandidate("unit", **b))
    kiwi = _kiwi()
    approved = []
    for name, detector in DETECTORS.items():
        decision = detector(pair, "observed", kiwi)
        if decision:
            approved.append(name)
            assert clauses[0][decision.source_start : decision.source_end] == candidate
        assert detector(pair, "uncertain", kiwi) is None
    assert tuple(approved) == expected
