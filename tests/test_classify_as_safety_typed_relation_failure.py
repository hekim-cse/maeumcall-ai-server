"""Check finite diagnostic reasons without retaining response text."""

import json

import pytest

from scripts.classify_as_safety_typed_relation_failure import REASONS, classify_candidate


def response(**changes) -> str:
    """Build a two-clause candidate response."""
    value = {
        "product_index": 1,
        "event_index": 2,
        "source_index": 2,
        "occurrence_index": 2,
        "source_relation": "current_product",
        "event_status": "observed",
    }
    value.update(changes)
    return json.dumps(value)


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("{", "json_syntax"),
        ("[]", "field_set"),
        (response(extra="private text"), "field_set"),
        (response(product_index="1"), "index_type"),
        (response(product_index=3), "enum"),
        (response(source_relation="nearby"), "enum"),
        (response(source_relation="none"), "empty_event_conflict"),
        (response(product_index=None), "missing_target"),
        (response(event_index=None), "missing_event_or_occurrence"),
        (response(source_index=None), "missing_source"),
    ],
)
def test_failure_is_finite_and_omits_response(raw: str, reason: str) -> None:
    """The classifier exposes only the expected fixed code."""
    decision, observed = classify_candidate(raw, 2)
    assert decision is None
    assert observed == reason
    assert observed in REASONS


def test_valid_response_preserves_only_bounded_decision() -> None:
    """A valid response has no error code."""
    decision, reason = classify_candidate(response(), 2)
    assert reason is None
    assert decision is not None
    assert decision["source_relation"] == "current_product"
