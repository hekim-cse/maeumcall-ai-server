"""Source IDs and routing for the development-only A/S relation candidate."""

import json

import pytest

from scripts.probe_as_safety_relation import (
    CONFIRM,
    DIRECT,
    NORMAL,
    relation_schema,
    route_relation,
    validate_relation,
)


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        ((1, 2, "current", "observed"), DIRECT),
        ((1, 2, "current", "uncertain"), CONFIRM),
        ((None, 2, "unknown", "observed"), CONFIRM),
        ((1, 2, "other", "observed"), NORMAL),
        ((1, 2, "current", "nonoccurring"), NORMAL),
        ((None, None, "none", "none"), NORMAL),
    ],
)
def test_relation_routes_are_distinct(decision: tuple, expected: str) -> None:
    product, hazard, target, event = decision
    parsed = validate_relation(
        json.dumps(
            {
                "product_index": product,
                "hazard_index": hazard,
                "target_relation": target,
                "event_status": event,
            }
        ),
        2,
    )
    assert route_relation(parsed) == expected


@pytest.mark.parametrize(
    "change",
    [
        {"product_index": 0},
        {"hazard_index": 3},
        {"hazard_index": True},
        {"target_relation": "self"},
        {"event_status": "positive"},
        {"product_index": None},
        {"hazard_index": None},
        {"target_relation": "none"},
        {"event_status": "none"},
        {"raw_text": "do not save this"},
    ],
)
def test_relation_rejects_invalid_contract(change: dict) -> None:
    decision = {
        "product_index": 1,
        "hazard_index": 2,
        "target_relation": "current",
        "event_status": "observed",
    }
    decision.update(change)
    with pytest.raises(ValueError):
        validate_relation(json.dumps(decision), 2)


def test_schema_uses_only_actual_clause_ids() -> None:
    schema = relation_schema(2)
    assert schema["properties"]["product_index"]["enum"] == [None, 1, 2]
    assert schema["properties"]["hazard_index"]["enum"] == [None, 1, 2]
    with pytest.raises(ValueError):
        relation_schema(0)
