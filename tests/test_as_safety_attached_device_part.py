"""Exercise boundary recovery without running the new review fixture."""

import json

import pytest

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_atomic_edges_v12.run import _kiwi
from experiments.as_safety_device_part import (
    attached_device_source,
    has_unique_device_split,
    names_extended_component,
    surface_nominal_source,
)
from experiments.as_safety_surface_nominal_evaluation import DATA
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate


@pytest.mark.parametrize("case_id", ["SN07", "SN08"])
def test_recovers_the_previously_missed_direct_sources(case_id):
    case = next(item for item in json.loads(DATA.read_bytes())["cases"] if item["id"] == case_id)
    candidate = next(item for item in case["candidates"] if item["approve"])
    clauses = split_clauses(case["utterance"])
    event = anchor_span(case["event"], clauses, field="event")
    span = anchor_span(candidate["span"], clauses, field="candidate")
    pair = FixedPair(case["utterance"], clauses, event, SourceCandidate(candidate["id"], **span))
    assert surface_nominal_source(pair, case["occurrence"], _kiwi()) is None
    result = attached_device_source(pair, case["occurrence"], _kiwi())
    assert result is not None
    assert (
        clauses[result.clause_index - 1][result.source_start : result.source_end] == span["quote"]
    )


@pytest.mark.parametrize(
    ("quote", "expected"),
    [
        ("세탁기여과판", True),
        ("전원 장치차폐격자", True),
        ("전원장치차폐격자", False),
        ("세탁기여과판옆", False),
        ("세탁기여과판 보관함", False),
        ("세탁기용여과판", False),
        ("세탁기  여과판", False),
    ],
)
def test_recognizes_only_the_complete_candidate(quote, expected):
    assert names_extended_component(quote) is expected


def test_rejects_a_compound_with_two_possible_splits():
    assert not has_unique_device_split(
        "기기차폐막",
        frozenset({"기기", "기기차"}),
        frozenset({"차폐", "폐"}),
        frozenset({"막"}),
    )
