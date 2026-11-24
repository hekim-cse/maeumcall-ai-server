"""Check event scope with unit cases separate from the new review set."""

import pytest

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_atomic_edges_v12.run import _kiwi
from experiments.as_safety_source_scope import source_scope
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate


@pytest.mark.parametrize(
    ("candidate", "event", "following", "approved"),
    [
        ("현관", "불꽃이 튀었습니다", "", False),
        ("케이블 단자 보관함", "불꽃이 튀었습니다", "", False),
        ("케이블 단자", "불꽃이 튀었습니다", "", True),
        ("케이블 단자", "불꽃이 튀었습니다", " 소음의 출처는 모르겠습니다.", True),
        ("케이블 단자", "불꽃이 튀었습니다", " 스파크의 출처는 모르겠습니다.", False),
        ("케이블 단자", "불꽃이 튀었습니다", " 출처는 모르겠습니다.", False),
        ("케이블 단자", "불꽃이 튀었습니다", " 소음과 불꽃의 출처는 모르겠습니다.", False),
        ("케이블 단자", "불꽃이 튀었습니다", " 소음도 들렸지만 출처는 모르겠습니다.", False),
        ("케이블 단자", "연기가 났습니다", " 냄새의 출처는 모르겠습니다.", False),
        ("케이블 단자", "불꽃이 튀었습니다", " 합선이 있었는지는 모르겠습니다.", True),
    ],
)
def test_scoped_uncertainty_and_device_support(candidate, event, following, approved):
    utterance = f"{candidate}에서 {event}.{following}"
    clauses = split_clauses(utterance)
    event_span = anchor_span({"quote": event, "clause_index": 1}, clauses, field="event")
    span = anchor_span({"quote": candidate, "clause_index": 1}, clauses, field="candidate")
    pair = FixedPair(utterance, clauses, event_span, SourceCandidate("test", **span))
    assert (source_scope(pair, "observed", _kiwi()) is not None) == approved
