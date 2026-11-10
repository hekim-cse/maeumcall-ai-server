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
    """Build a finite model response for one two-clause utterance."""
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
            response("none", "none", product=None, event=None, source=None, occurrence=None),
            NORMAL,
        ),
    ],
)
def test_typed_relation_routes(raw: str, expected: str) -> None:
    """Every accepted relation has a deterministic bounded route."""
    decision = validate_typed_relation(raw, 2)
    assert route_typed_relation(decision) == expected
    schema = typed_relation_journal_schema(2)
    assert set(decision) == set(schema["required"])
    assert all(value in schema["properties"][field]["enum"] for field, value in decision.items())


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
    """Out-of-contract values cannot enter the decision journal."""
    decision = json.loads(response("current_part"))
    decision.update(change)
    with pytest.raises(ValueError):
        validate_typed_relation(json.dumps(decision), 2)


def test_no_event_requires_all_evidence_ids_null() -> None:
    """An empty event must not retain any source evidence."""
    with pytest.raises(ValueError):
        validate_typed_relation(response("none", "none"), 2)


@pytest.mark.parametrize("relation", ["unknown", "location_only", "alternative_unknown"])
def test_event_requires_service_target_evidence_for_every_source_relation(relation: str) -> None:
    """Any event must identify which service target it concerns."""
    with pytest.raises(ValueError, match="service target evidence"):
        validate_typed_relation(response(relation, product=None), 2)


def test_schema_is_finite_and_requires_actual_clauses() -> None:
    """The schema exposes only IDs from the source utterance."""
    schema = typed_relation_schema(2)
    assert schema == typed_relation_journal_schema(2)
    assert schema["properties"]["source_index"]["enum"] == [None, 1, 2]
    with pytest.raises(ValueError):
        typed_relation_schema(0)


@pytest.mark.parametrize("raw", ["", "{", "[]", "null", '"text"', "1"])
def test_malformed_or_nonobject_model_responses_are_rejected(raw: str) -> None:
    """Malformed JSON and JSON values other than objects fail validation."""
    with pytest.raises(ValueError):
        validate_typed_relation(raw, 2)


@pytest.mark.parametrize(
    "field", ["product_index", "event_index", "source_index", "occurrence_index"]
)
@pytest.mark.parametrize("value", [-1, 0, 3, True, 1.0, "1", [], {}])
def test_every_evidence_id_must_be_a_valid_integer_clause(field: str, value: object) -> None:
    """No edge can point outside the original clauses or use a coercible type."""
    decision = json.loads(response("current_product"))
    decision[field] = value
    with pytest.raises(ValueError):
        validate_typed_relation(json.dumps(decision), 2)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_relation", "current"),
        ("source_relation", None),
        ("source_relation", 1),
        ("event_status", "negated"),
        ("event_status", None),
        ("event_status", 1),
    ],
)
def test_unknown_enum_values_are_rejected(field: str, value: object) -> None:
    """Only the reviewed relation and occurrence categories are accepted."""
    decision = json.loads(response("current_product"))
    decision[field] = value
    with pytest.raises(ValueError):
        validate_typed_relation(json.dumps(decision), 2)
