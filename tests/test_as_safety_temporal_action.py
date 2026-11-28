"""Test independent locative boundaries using examples outside the review fixture."""

import pytest

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_atomic_edges_v12.run import _kiwi
from experiments.as_safety_temporal_action import RULES
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate


@pytest.mark.parametrize(
    ("prefix", "quote", "event", "suffix", "expected"),
    [
        ("", "멀티탭 단자", "불꽃이 튀었습니다", ".", tuple(RULES)),
        ("방금 ", "멀티탭 단자", "불꽃이 튀었습니다", ".", ("time_only", "time_and_action")),
        (
            "",
            "멀티탭 단자",
            "불꽃이 튀어서",
            " 전원을 차단했습니다.",
            ("action_only", "time_and_action"),
        ),
        (
            "엊그제 밤 ",
            "멀티탭 단자",
            "불꽃이 튀어서",
            " 전원을 차단했습니다.",
            ("time_and_action",),
        ),
        ("방금 창고에서 ", "멀티탭 단자", "불꽃이 튀었습니다", ".", ()),
        ("방금 ", "창고 선반", "불꽃이 튀었습니다", ".", ()),
        ("", "멀티탭 단자", "불꽃이 튀면", " 전원을 차단했습니다.", ()),
        ("", "멀티탭 단자", "불꽃이 튀어서", " 전원을 차단했지만 출처는 모르겠습니다.", ()),
        (
            "",
            "멀티탭 단자",
            "불꽃이 튀어서",
            " 전원을 차단했습니다. 불꽃의 출처는 모르겠습니다.",
            (),
        ),
        ("", "멀티탭 단자", "불꽃을 보고", " 전원을 차단했습니다.", ()),
        ("", "멀티탭 단자", "불꽃이 튀어서", " 전원을 차단했고, 배터리에서 연기가 났습니다.", ()),
    ],
)
def test_independent_source_boundaries(prefix, quote, event, suffix, expected):
    source = f"{prefix}{quote}에서 {event}{suffix}"
    clauses = split_clauses(source)
    e = anchor_span({"clause_index": 1, "quote": event}, clauses, field="event")
    b = anchor_span({"clause_index": 1, "quote": quote}, clauses, field="source")
    pair = FixedPair(source, clauses, e, SourceCandidate("unit", **b))
    kiwi = _kiwi()

    approved = []
    for name, detector in RULES.items():
        result = detector(pair, "observed", kiwi)
        if result is not None:
            approved.append(name)
            assert clauses[0][result.source_start : result.source_end] == quote
        assert detector(pair, "nonoccurring", kiwi) is None
    assert tuple(approved) == expected
