"""Source lattice behavior, without making semantic relation claims."""

import hashlib
import inspect

import pytest

from experiments.as_safety_v2.quotes import split_clauses
from experiments.as_safety_v2.source_lattice import (
    generate_source_lattice,
    source_candidate_status,
)


def _matches(lattice, quote):
    return [candidate for candidate in lattice.candidates if candidate.quote == quote]


def test_combined_and_single_character_postpositions_are_source_spans():
    message = (
        "접수할 의자가 멈췄습니다. 등받이 뒤에서 불꽃이 났어요. "
        "전동 드릴 배터리에서는 연기가 났습니다. 전자담배 충전기에서는 열이 났습니다."
    )
    lattice = generate_source_lattice(message)
    clauses = split_clauses(message)
    for quote in ("등받이 뒤", "전동 드릴 배터리", "전자담배 충전기"):
        matches = _matches(lattice, quote)
        assert len(matches) == 1
        item = matches[0]
        assert clauses[item.clause_index - 1][item.start : item.end] == quote
        assert item.quote_sha256 == hashlib.sha256(quote.encode("utf-8")).hexdigest()


def test_duplicate_source_text_keeps_distinct_offsets():
    message = "충전기에서 충전기에서 연기가 났어요."
    lattice = generate_source_lattice(message)
    matches = _matches(lattice, "충전기")
    assert len(matches) == 2
    assert len({(item.clause_index, item.start, item.end) for item in matches}) == 2
    assert len({item.id for item in lattice.candidates}) == len(lattice.candidates)
    assert generate_source_lattice(message) == lattice


def test_bounded_selection_reports_truncation_separately_from_generation():
    message = "접수할 의자가 멈췄습니다. 등받이 뒤에서 불꽃이 났어요."
    full = generate_source_lattice(message)
    bounded = generate_source_lattice(message, max_candidates=1)
    target = _matches(full, "등받이 뒤")[0]
    assert bounded.truncated
    assert source_candidate_status(
        bounded,
        clause_index=target.clause_index,
        start=target.start,
        end=target.end,
    ) == "truncated"
    assert source_candidate_status(
        full,
        clause_index=target.clause_index,
        start=target.start,
        end=target.end,
    ) == "selected"
    assert source_candidate_status(bounded, clause_index=2, start=999, end=1000) == "not_generated"


def test_generator_has_no_reviewed_label_input_and_validates_limits():
    signature = inspect.signature(generate_source_lattice)
    assert set(signature.parameters) == {"user_message", "max_window_tokens", "max_candidates"}
    for kwargs in (
        {"max_window_tokens": 0},
        {"max_window_tokens": True},
        {"max_candidates": 0},
        {"max_candidates": 257},
        {"max_candidates": True},
    ):
        with pytest.raises(ValueError):
            generate_source_lattice("제품에서 연기가 났어요.", **kwargs)
