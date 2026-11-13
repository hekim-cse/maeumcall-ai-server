"""Protect source provenance and bounded contract failure reporting."""

from __future__ import annotations

import hashlib

import pytest

from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.quotes import anchor_span, split_clauses


def test_clause_ids_preserve_original_unicode_text():
    assert split_clauses("제품은 TV입니다. 그 제품에서 연기가 났어요!") == (
        "제품은 TV입니다.",
        "그 제품에서 연기가 났어요!",
    )


def test_quote_offset_and_hash_count_unicode_codepoints():
    clause = "어젯밤 그 제품에서 연기가 났어요."
    anchored = anchor_span({"clause_index": 1, "quote": "그 제품"}, (clause,), field="owner_span")
    assert anchored == {
        "clause_index": 1,
        "quote": "그 제품",
        "start": clause.index("그 제품"),
        "end": clause.index("그 제품") + len("그 제품"),
        "quote_sha256": hashlib.sha256("그 제품".encode()).hexdigest(),
    }


@pytest.mark.parametrize(
    ("item", "clauses", "expected_code"),
    [
        ({"clause_index": 1, "quote": "원문"}, ("제품에서 연기가 났어요.",), "quote_unanchored"),
        ({"clause_index": 1, "quote": "TV"}, ("TV 옆 TV에서 연기",), "quote_nonunique"),
        ({"clause_index": 1, "quote": "aa"}, ("aaa",), "quote_nonunique"),
        ({"clause_index": True, "quote": "TV"}, ("TV",), "quote_index_invalid"),
        ({"clause_index": 2, "quote": "TV"}, ("TV",), "quote_index_invalid"),
        ({"clause_index": 1, "quote": " TV"}, (" TV",), "quote_blank"),
        ({"clause_index": 1, "quote": "TV", "extra": 1}, ("TV",), "quote_fields_invalid"),
    ],
)
def test_quote_failure_is_field_specific_and_does_not_echo_input(item, clauses, expected_code):
    with pytest.raises(ValidationError) as caught:
        anchor_span(item, clauses, field="owner_span")
    assert (caught.value.code, caught.value.field) == (expected_code, "owner_span")
    assert "제품에서 연기가" not in str(caught.value)


def test_null_quote_is_preserved_for_explicit_abstention():
    assert anchor_span(None, ("연기가 났어요.",), field="owner_span") is None


def test_duplicate_key_is_rejected_inside_nested_object():
    raw = '{"owner_span":{"clause_index":1,"quote":"TV","quote":"원문"}}'
    with pytest.raises(ValidationError) as caught:
        parse_model_json(raw)
    assert (caught.value.code, caught.value.field) == ("duplicate_key", "quote")


@pytest.mark.parametrize(
    ("raw", "expected_code"),
    [("{", "invalid_json"), ('{"x":NaN}', "nonfinite_number"), (None, "response_type_invalid")],
)
def test_json_failure_codes_are_bounded(raw, expected_code):
    with pytest.raises(ValidationError) as caught:
        parse_model_json(raw)
    assert (caught.value.code, caught.value.field) == (expected_code, "$")
