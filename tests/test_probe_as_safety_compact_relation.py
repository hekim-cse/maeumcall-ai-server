"""Contract tests for the compact, development-only A/S safety candidate."""

import json

import pytest

from scripts.probe_as_safety_compact_relation import (
    CONFIRM,
    DIRECT,
    NORMAL,
    compact_relation_journal_schema,
    compact_relation_schema,
    route_compact_relation,
    validate_compact_relation,
)


def response(
    relation="current_product",
    status="observed",
    *,
    product=1,
    event=1,
    source=1,
):
    """Build one finite model response with independently changeable evidence."""
    return json.dumps(
        {
            "product_index": product,
            "event_index": event,
            "source_index": source,
            "source_relation": relation,
            "event_status": status,
        }
    )


@pytest.mark.parametrize(
    ("raw", "route"),
    [
        (response(), DIRECT),
        (response("current_part", event=2, source=2), DIRECT),
        (response("other_product", event=2, source=2), NORMAL),
        (response("location_only", event=1, source=1), CONFIRM),
        (response("alternative_unknown", event=1, source=2), CONFIRM),
        (response("unknown", source=None), CONFIRM),
        (response(status="uncertain"), CONFIRM),
        (response(status="nonoccurring"), NORMAL),
        (response("none", "none", product=None, event=None, source=None), NORMAL),
    ],
)
def test_routes_preserve_event_and_source_distinction(raw, route):
    """A later source correction can coexist with an earlier observed event."""
    decision = validate_compact_relation(raw, 2)
    assert route_compact_relation(decision) == route
    schema = compact_relation_journal_schema(2)
    assert set(decision) == set(schema["required"])


@pytest.mark.parametrize(
    "change",
    [
        {"product_index": None},
        {"event_index": None},
        {"source_index": None},
        {"event_index": 3},
        {"source_index": True},
        {"source_relation": "same"},
        {"event_status": "certain"},
        {"source_relation": "none"},
        {"event_status": "none"},
        {"extra": "raw text"},
    ],
)
def test_invalid_or_missing_evidence_fails_contract(change):
    """Do not turn missing or unbounded evidence into a scored route."""
    value = json.loads(response())
    value.update(change)
    with pytest.raises(ValueError):
        validate_compact_relation(json.dumps(value), 2)


@pytest.mark.parametrize("raw", ["", "{", "[]", "null", "42"])
def test_non_object_or_invalid_json_rejected(raw):
    """Malformed or non-object model output cannot satisfy the contract."""
    with pytest.raises(ValueError):
        validate_compact_relation(raw, 2)


def test_no_event_requires_all_indices_empty():
    """A no-event judgment cannot carry stray product or source evidence."""
    with pytest.raises(ValueError):
        validate_compact_relation(response("none", "none"), 2)


def test_schema_is_finite_and_requires_clauses():
    """The response and journal shapes have the same bounded fields."""
    assert compact_relation_schema(2) == compact_relation_journal_schema(2)
    assert compact_relation_schema(2)["properties"]["event_index"]["enum"] == [None, 1, 2]
    with pytest.raises(ValueError):
        compact_relation_schema(0)
