"""Focused contract checks for the development-only typed safety candidate."""

import json

import pytest

from scripts.probe_as_safety_typed_relation import (
    CONFIRM,
    DIRECT,
    NORMAL,
    route_typed_relation,
    typed_relation_journal_schema,
    typed_relation_schema,
    validate_typed_relation,
)


def response(
    relation: str,
    status: str = "observed",
    *,
    product: int | None = 1,
    event: int | None = 2,
    source: int | None = 2,
    occurrence: int | None = 2,
) -> str:
    return json.dumps(
        {
            "product_index": product,
            "event_index": event,
            "source_index": source,
            "occurrence_index": occurrence,
            "source_relation": relation,
            "event_status": status,
        }
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (response("current_product"), DIRECT),
        (response("current_part"), DIRECT),
        (response("other_product"), NORMAL),
        (response("other_product", "uncertain"), NORMAL),
        (response("location_only", event=1, source=1, occurrence=1), CONFIRM),
        (response("alternative_unknown", event=1, source=2, occurrence=1), CONFIRM),
        (response("unknown", source=None), CONFIRM),
        (response("current_product", "uncertain"), CONFIRM),
        (response("current_part", "nonoccurring"), NORMAL),
        (
            response(
                "none", "none", product=None, event=None, source=None, occurrence=None
            ),
            NORMAL,
        ),
    ],
)
def test_typed_relation_routes(raw: str, expected: str) -> None:
    decision = validate_typed_relation(raw, 2)
    assert route_typed_relation(decision) == expected
    schema = typed_relation_journal_schema(2)
    assert set(decision) == set(schema["required"])
    assert all(
        value in schema["properties"][field]["enum"]
        for field, value in decision.items()
    )


@pytest.mark.parametrize(
    "change",
    [
        {"product_index": True},
        {"event_index": 0},
        {"source_index": 3},
        {"occurrence_index": None},
        {"source_index": None},
        {"product_index": None},
        {"source_relation": "same"},
        {"event_status": "certain"},
        {"source_relation": "none"},
        {"event_status": "none"},
        {"free_text": "do not journal this"},
    ],
)
def test_invalid_or_unbounded_decisions_rejected(change: dict) -> None:
    decision = json.loads(response("current_part"))
    decision.update(change)
    with pytest.raises(ValueError):
        validate_typed_relation(json.dumps(decision), 2)


def test_no_event_requires_all_evidence_ids_null() -> None:
    with pytest.raises(ValueError):
        validate_typed_relation(response("none", "none"), 2)


@pytest.mark.parametrize("relation", ["unknown", "location_only", "alternative_unknown"])
def test_event_requires_service_target_evidence_for_every_source_relation(relation: str) -> None:
    with pytest.raises(ValueError, match="service target evidence"):
        validate_typed_relation(response(relation, product=None), 2)


def test_schema_is_finite_and_requires_actual_clauses() -> None:
    schema = typed_relation_schema(2)
    assert schema == typed_relation_journal_schema(2)
    assert schema["properties"]["source_index"]["enum"] == [None, 1, 2]
    with pytest.raises(ValueError):
        typed_relation_schema(0)
