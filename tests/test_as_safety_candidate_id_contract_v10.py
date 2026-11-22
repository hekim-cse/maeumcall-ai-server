"""Offline checks for the development-only candidate-ID contract."""

import json
from dataclasses import replace

import pytest
from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v10.candidate_contract import (
    catalog_from_candidates,
    nominal_catalog,
)
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.source_lattice import generate_source_lattice

SOURCE = "선풍기를 접수하려고 합니다. 선풍기 모터에서 연기가 났습니다."


def _catalog():
    lattice = generate_source_lattice(SOURCE)
    selected = tuple(c for c in lattice.candidates if c.quote in {"선풍기 모터", "선풍기 모터에서"})
    assert len(selected) == 2
    return catalog_from_candidates(SOURCE, selected)


def _wire(candidate_id, kind):
    return json.dumps({"candidate_id": candidate_id, "event_subject_kind": kind})


def test_selected_id_maps_to_exact_source_span_and_no_quote_is_accepted():
    catalog = _catalog()
    bare = next(c for c in catalog.candidates if c.quote == "선풍기 모터")
    result = catalog.resolve(_wire(bare.id, "location"))
    assert result == {
        "candidate_id": bare.id,
        "subject_span": {"clause_index": 2, "quote": "선풍기 모터"},
        "event_subject_kind": "location",
    }
    assert set(catalog.schema()["properties"]) == {"candidate_id", "event_subject_kind"}
    assert catalog.schema()["properties"]["candidate_id"]["anyOf"][0]["enum"] == [
        c.id for c in catalog.candidates
    ]


def test_explicit_unresolved_hold_is_valid_even_with_available_candidates():
    assert _catalog().resolve(_wire(None, "unresolved")) == {
        "candidate_id": None,
        "subject_span": None,
        "event_subject_kind": "unresolved",
    }


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (_wire("P999", "location"), "candidate_not_offered"),
        (_wire("선풍기 모터", "location"), "candidate_not_offered"),
        (_wire("P001 ", "location"), "candidate_not_offered"),
        (_wire(None, "location"), "selection_consistency_invalid"),
        (_wire(None, "invented"), "subject_kind_invalid"),
        (_wire(False, "location"), "candidate_id_invalid"),
        ('{"candidate_id":null,"event_subject_kind":"unresolved","extra":1}', "fields_invalid"),
        (
            '{"candidate_id":null,"candidate_id":null,"event_subject_kind":"unresolved"}',
            "duplicate_key",
        ),
        ('{"candidate_id":null,"event_subject_kind":"unresolved","x":NaN}', "nonfinite_number"),
    ],
)
def test_contract_rejects_unoffered_or_malformed_output(raw, code):
    with pytest.raises(ValidationError) as error:
        _catalog().resolve(raw)
    assert error.value.code == code


def test_resolved_id_cannot_claim_unresolved_kind():
    candidate_id = _catalog().candidates[0].id
    with pytest.raises(ValidationError) as error:
        _catalog().resolve(_wire(candidate_id, "unresolved"))
    assert error.value.code == "selection_consistency_invalid"


@pytest.mark.parametrize(
    "mutation", ["duplicate_id", "duplicate_span", "wrong_quote", "wrong_hash"]
)
def test_catalog_rejects_tampered_candidate_source(mutation):
    catalog = _catalog()
    first, second = catalog.candidates
    if mutation == "duplicate_id":
        changed = replace(second, id=first.id)
    elif mutation == "duplicate_span":
        changed = replace(
            second,
            start=first.start,
            end=first.end,
            quote=first.quote,
            quote_sha256=first.quote_sha256,
        )
    elif mutation == "wrong_quote":
        changed = replace(second, quote="원문에 없는 구절")
    else:
        changed = replace(second, quote_sha256="0" * 64)
    with pytest.raises(ValueError):
        catalog_from_candidates(SOURCE, (first, changed))


def test_catalog_rejects_empty_candidate_set():
    with pytest.raises(ValueError, match="empty"):
        catalog_from_candidates(SOURCE, ())


def test_nominal_catalog_is_generated_from_source_without_gold():
    catalog = nominal_catalog(SOURCE, Kiwi())
    assert any(c.quote == "선풍기 모터" for c in catalog.candidates)
    assert all(
        SOURCE.split(". ")[c.clause_index - 1].find(c.quote) >= 0 for c in catalog.candidates
    )
