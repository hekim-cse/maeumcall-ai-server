"""Target the observed entity and location boundary, without using evaluation data."""

import pytest

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_source_role import source_role
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate


@pytest.mark.parametrize(
    ("text", "event", "candidate", "expected"),
    [
        ("상자에서 병이 갈라졌습니다.", "병이 갈라졌습니다", "병", True),
        ("상자에서 병이 갈라졌습니다.", "병이 갈라졌습니다", "상자", False),
        ("창가에서 연기가 보였습니다.", "연기가 보였습니다", "창가", False),
        (
            "공구함에서 연기가 났습니다. 출처를 확인하지 못했습니다.",
            "연기가 났습니다",
            "공구함",
            False,
        ),
        (
            "공구함에서 연기가 났습니다. 어디서 수리할지 모르겠습니다.",
            "연기가 났습니다",
            "공구함",
            True,
        ),
        ("상자에서 병이 갈라지지 않았습니다.", "병이 갈라지지 않았습니다", "병", False),
    ],
)
def test_source_roles(text, event, candidate, expected):
    from experiments.as_safety_atomic_edges_v12.run import _kiwi

    clauses = split_clauses(text)
    anchor = anchor_span({"clause_index": 1, "quote": event}, clauses, field="event")
    span = anchor_span({"clause_index": 1, "quote": candidate}, clauses, field="candidate")
    pair = FixedPair(text, clauses, anchor, SourceCandidate("test", **span))
    answer = source_role(pair, "observed", _kiwi())
    assert (answer is not None) is expected
