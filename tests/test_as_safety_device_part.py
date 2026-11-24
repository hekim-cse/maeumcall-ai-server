"""Check newly composed part names without evaluating the review fixture."""

import pytest

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_atomic_edges_v12.run import _kiwi
from experiments.as_safety_device_part import composed_source, names_device_component
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("세탁기 방열망", True),
        ("전원 장치 절연판", True),
        ("세탁기 방열망 옆", False),
        ("세탁기 방열망 보관함", False),
        ("세탁기용 방열망", False),
        ("세탁기와 정수기 방열망", False),
        ("작업대 방열망", False),
        ("방열망", False),
    ],
)
def test_composition_requires_whole_device_and_part(phrase, expected):
    assert names_device_component(phrase) is expected


@pytest.mark.parametrize(
    ("candidate", "event", "continuation", "expected"),
    [
        ("세탁기 방열망", "연기가 났습니다", "", True),
        ("세탁기 방열망 옆", "연기가 났습니다", "", False),
        ("세탁기 방열망", "연기가 보였습니다", "", False),
        ("세탁기 방열망", "연기가 났습니다", " 연기가 어디서 났는지는 모르겠습니다.", False),
    ],
)
def test_composition_preserves_event_and_uncertainty_checks(
    candidate, event, continuation, expected
):
    utterance = f"{candidate}에서 {event}.{continuation}"
    clauses = split_clauses(utterance)
    observed = anchor_span({"quote": event, "clause_index": 1}, clauses, field="event")
    source = anchor_span({"quote": candidate, "clause_index": 1}, clauses, field="candidate")
    pair = FixedPair(utterance, clauses, observed, SourceCandidate("test", **source))
    assert (composed_source(pair, "observed", _kiwi()) is not None) is expected
