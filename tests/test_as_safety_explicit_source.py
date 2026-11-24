"""Check the offline baseline against candidate swaps and its abstention boundary."""

from dataclasses import replace

import pytest

from experiments.as_safety_atomic_edges_v10 import probe
from experiments.as_safety_atomic_edges_v12 import pair_contract, run
from experiments.as_safety_explicit_source import explicit_source
from experiments.as_safety_v2.quotes import anchor_span
from experiments.as_safety_v2.source_lattice import SourceCandidate


@pytest.mark.parametrize(
    ("case_id", "candidate_id", "expected"),
    [
        ("PC01", "P014", 2),
        ("PC01", "P016", None),
        ("NC01", "P020", None),
        ("NC01", "P002", None),
    ],
)
def test_same_event_candidate_comparison(case_id, candidate_id, expected):
    case = probe.cases()[case_id]
    kiwi = run._kiwi()
    pair = pair_contract.fixed_pair(case, candidate_id, kiwi)
    result = explicit_source(pair, case["occurrence"], kiwi)
    assert (result.clause_index if result else None) == expected


def test_requires_observed_event_and_complete_source_phrase():
    kiwi = run._kiwi()
    pair = pair_contract.fixed_pair(probe.cases()["PC01"], "P014", kiwi)
    assert explicit_source(pair, "uncertain", kiwi) is None
    shortened = replace(pair.candidate, start=4, quote="모터")
    assert explicit_source(replace(pair, candidate=shortened), "observed", kiwi) is None


def test_anchor_mismatch_is_error_not_abstention():
    kiwi = run._kiwi()
    pair = pair_contract.fixed_pair(probe.cases()["PC01"], "P014", kiwi)
    bad = replace(pair.candidate, quote="없는 문장")
    with pytest.raises(ValueError, match="candidate anchor differs"):
        explicit_source(replace(pair, candidate=bad), "observed", kiwi)


@pytest.mark.parametrize(
    ("prefix", "suffix", "accepted"),
    [
        ("충전기로부터 ", ".", True),
        ("충전기에서 ", "고 들었습니다.", False),
        ("충전기 옆에서 ", ".", False),
        ("충전기 앞에서 처음 ", ".", False),
    ],
)
def test_requires_direct_attachment_without_extra_words(prefix, suffix, accepted):
    quote = "불꽃이 튀었다"
    clause = prefix + quote + suffix
    event = anchor_span({"clause_index": 1, "quote": quote}, (clause,), field="event")
    candidate = SourceCandidate("example", 1, 0, len("충전기"), "충전기", "")
    pair = pair_contract.FixedPair(clause, (clause,), event, candidate)
    assert (explicit_source(pair, "observed", run._kiwi()) is not None) == accepted
