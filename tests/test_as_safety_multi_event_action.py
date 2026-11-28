"""Exercise event-local anchors and reject uncontrolled continuations."""

import pytest

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_atomic_edges_v12.run import _kiwi
from experiments.as_safety_multi_event_action import DETECTORS
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate

FIRST = "냉각 장치 단자에서 불꽃이 튀어 전원을 껐고, "
SECOND = "건조기 커넥터에서 연기가 나왔습니다."


@pytest.mark.parametrize(
    ("source", "event", "candidate", "selected"),
    [
        (FIRST + SECOND, "불꽃이 튀어", "냉각 장치 단자", True),
        (FIRST + SECOND, "불꽃이 튀어", "건조기 커넥터", False),
        (FIRST + SECOND, "연기가 나왔습니다", "냉각 장치 단자", False),
        (FIRST + SECOND, "연기가 나왔습니다", "건조기 커넥터", True),
        (FIRST + "창고 출입구에서 연기를 봤습니다.", "연기를 봤습니다", "창고 출입구", False),
        (FIRST + "점검을 부탁합니다.", "불꽃이 튀어", "냉각 장치 단자", False),
        (
            FIRST + "건조기 커넥터에서 연기가 났지만 불꽃의 출처는 모르겠습니다.",
            "불꽃이 튀어",
            "냉각 장치 단자",
            False,
        ),
        (
            FIRST + SECOND + " 불꽃의 출처는 모르겠습니다.",
            "불꽃이 튀어",
            "냉각 장치 단자",
            False,
        ),
    ],
)
def test_selection_is_local_to_anchored_event(source, event, candidate, selected):
    clauses = split_clauses(source)
    e = anchor_span({"clause_index": 1, "quote": event}, clauses, field="event")
    b = anchor_span({"clause_index": 1, "quote": candidate}, clauses, field="candidate")
    pair = FixedPair(source, clauses, e, SourceCandidate("unit", **b))
    kiwi = _kiwi()
    assert DETECTORS["baseline"](pair, "observed", kiwi) is None
    result = DETECTORS["multi_event"](pair, "observed", kiwi)
    assert (result is not None) is selected
    if result is not None:
        assert clauses[0][result.source_start : result.source_end] == candidate
    assert DETECTORS["multi_event"](pair, "uncertain", kiwi) is None
