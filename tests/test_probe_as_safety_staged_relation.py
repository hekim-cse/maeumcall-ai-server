"""Focused finite-contract checks for the development-only staged candidate."""

import json

import pytest

from scripts.probe_as_safety_staged_relation import (
    CONFIRM,
    DIRECT,
    NORMAL,
    combine_stages,
    event_schema,
    journal_schema,
    route_staged,
    source_schema,
    validate_event,
    validate_source,
)


def event(index: int | None = 1, status: str = "observed") -> dict:
    """Build one bounded event-stage decision."""
    return {"event_index": index, "event_status": status}


def source(relation: str = "current_product", index: int | None = 1) -> dict:
    """Build one bounded source-stage decision."""
    return {"product_index": 1, "source_index": index, "source_relation": relation}


@pytest.mark.parametrize(
    ("event_decision", "source_decision", "expected"),
    [
        (event(), source(), DIRECT),
        (event(), source("current_part"), DIRECT),
        (event(), source("other_product"), NORMAL),
        (event(), source("location_only"), CONFIRM),
        (event(), source("alternative_unknown", 2), CONFIRM),
        (event(), source("unknown", None), CONFIRM),
        (event(1, "uncertain"), source(), CONFIRM),
        (event(1, "uncertain"), source("other_product"), NORMAL),
        (event(1, "nonoccurring"), None, NORMAL),
        (event(None, "none"), None, NORMAL),
    ],
)
def test_staged_routes(event_decision: dict, source_decision: dict | None, expected: str) -> None:
    """Separate event occurrence and source attribution in the final route."""
    decision = combine_stages(event_decision, source_decision)
    assert route_staged(decision) == expected
    schema = journal_schema(2)
    assert set(decision) == set(schema["required"])
    assert all(value in schema["properties"][field]["enum"] for field, value in decision.items())


@pytest.mark.parametrize(
    "payload",
    [
        {"event_index": None, "event_status": "observed"},
        {"event_index": 1, "event_status": "none"},
        {"event_index": True, "event_status": "observed"},
        {"event_index": 0, "event_status": "observed"},
        {"event_index": -1, "event_status": "observed"},
        {"event_index": 1.0, "event_status": "observed"},
        {"event_index": "1", "event_status": "observed"},
        {"event_index": 3, "event_status": "observed"},
        {"event_index": 1, "event_status": " "},
        {"event_index": 1, "event_status": "happened"},
        {"event_index": 1, "event_status": "observed", "raw": "text"},
        [],
        None,
    ],
)
def test_invalid_event_fails(payload) -> None:
    """Missing, malformed, and unbounded stage-one evidence must fail."""
    with pytest.raises(ValueError):
        validate_event(json.dumps(payload), 2)


@pytest.mark.parametrize(
    "payload",
    [
        {"product_index": None, "source_index": 1, "source_relation": "current_product"},
        {"product_index": True, "source_index": 1, "source_relation": "current_product"},
        {"product_index": 1, "source_index": None, "source_relation": "current_product"},
        {"product_index": 1, "source_index": 3, "source_relation": "current_product"},
        {"product_index": 1, "source_index": True, "source_relation": "current_product"},
        {"product_index": 1, "source_index": 1, "source_relation": " "},
        {"product_index": 1, "source_index": 1, "source_relation": 1},
        {
            "product_index": 1,
            "source_index": 1,
            "source_relation": "current_product",
            "raw": "text",
        },
    ],
)
def test_invalid_source_fails(payload: dict) -> None:
    """Stage two must not invent a product or accept an unsupported relation."""
    with pytest.raises(ValueError):
        validate_source(json.dumps(payload), 2)


def test_stage_boundary_and_schemas() -> None:
    """Only observed or uncertain events may trigger the source stage."""
    assert validate_event(json.dumps(event(1, "nonoccurring")), 2) == event(1, "nonoccurring")
    assert validate_source(json.dumps(source("unknown", None)), 2) == source("unknown", None)
    with pytest.raises(ValueError, match="source stage must be skipped"):
        combine_stages(event(1, "nonoccurring"), source())
    with pytest.raises(ValueError, match="source stage is required"):
        combine_stages(event(), None)
    assert source_schema(2)["properties"]["product_index"]["enum"] == [1, 2]
    assert event_schema(2)["properties"]["event_index"]["enum"] == [None, 1, 2]


@pytest.mark.parametrize(
    "malformed_event",
    [
        {"event_index": 1},
        {"event_index": 1, "event_status": "observed", "raw": "text"},
        None,
    ],
)
def test_combine_rejects_malformed_event_structure(malformed_event) -> None:
    """The stage boundary must not accept an incomplete event decision."""
    with pytest.raises(ValueError, match="event decision fields differ"):
        combine_stages(malformed_event, source())


@pytest.mark.parametrize(
    "malformed_decision",
    [
        {},
        {"event_index": 1, "event_status": "observed"},
        None,
    ],
)
def test_route_rejects_malformed_combined_structure(malformed_decision) -> None:
    """No route may be scored from a missing or non-object decision."""
    with pytest.raises(ValueError, match="staged decision fields differ"):
        route_staged(malformed_decision)
