"""Check pad evidence, explicit adjacency, and colloquial action boundaries."""

import pytest

from experiments.as_safety_adjacent_pad_source import DETECTORS
from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_atomic_edges_v12.run import _kiwi
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate

INTRO = "탁자에 조명을 놓았어요. "
PAD = "휴대용 무선 충전 패드"
DIRECT = f"{INTRO}그 옆의 {PAD}에서 불꽃이 튀어 플러그를 뽑았어요."
SEPARATE_SPARK = " 별도로 선풍기에서도 불꽃이 튀었습니다."


@pytest.mark.parametrize(
    ("source", "index", "candidate", "event", "expected"),
    [
        (DIRECT, 2, PAD, "불꽃이 튀어", True),
        (DIRECT, 2, "무선 충전 패드", "불꽃이 튀어", False),
        (DIRECT, 2, "플러그", "불꽃이 튀어", False),
        (DIRECT.removeprefix(INTRO), 1, PAD, "불꽃이 튀어", False),
        (f"{PAD}에서 불꽃이 튀었습니다.", 1, PAD, "불꽃이 튀었습니다", True),
        (f"{PAD} 옆에서 불꽃을 보고 플러그를 뽑았어요.", 1, f"{PAD} 옆", "불꽃을 보고", False),
        (
            f"{PAD} 옆 작업대에서 불꽃이 튀어 플러그를 뽑았어요.",
            1,
            f"{PAD} 옆 작업대",
            "불꽃이 튀어",
            False,
        ),
        (f"{PAD}에서 불꽃이 튀어 플러그를 뽑으려 했어요.", 1, PAD, "불꽃이 튀어", False),
        (
            DIRECT + " 다시 보니 불꽃은 선풍기 단자에서 튀었어요.",
            2,
            PAD,
            "불꽃이 튀어",
            False,
        ),
        (DIRECT + f" 다시 보니 {PAD}가 아니라 선풍기 단자였어요.", 2, PAD, "불꽃이 튀어", False),
        (
            DIRECT
            + SEPARATE_SPARK
            + " 다시 보니 선풍기의 불꽃은 단자가 아니라 전원선에서 튀었어요.",
            2,
            PAD,
            "불꽃이 튀어",
            True,
        ),
        (
            DIRECT + SEPARATE_SPARK + " 다시 보니 첫 불꽃은 멀티탭 단자에서 튀었어요.",
            2,
            PAD,
            "불꽃이 튀어",
            False,
        ),
        (DIRECT + f" {PAD}는 작업실 이름입니다.", 2, PAD, "불꽃이 튀어", False),
    ],
)
def test_adjacent_pad_anchors_actual_source(source, index, candidate, event, expected):
    clauses = split_clauses(source)
    e = anchor_span({"clause_index": index, "quote": event}, clauses, field="event")
    b = anchor_span({"clause_index": index, "quote": candidate}, clauses, field="source")
    pair = FixedPair(source, clauses, e, SourceCandidate("unit", **b))
    kiwi = _kiwi()
    assert DETECTORS["baseline"](pair, "observed", kiwi) is None
    result = DETECTORS["adjacent_pad"](pair, "observed", kiwi)
    assert (result is not None) is expected
    if result is not None:
        assert clauses[index - 1][result.source_start : result.source_end] == candidate
    assert DETECTORS["adjacent_pad"](pair, "uncertain", kiwi) is None
