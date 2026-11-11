"""Keep the rejected gold-span development result separate from fresh GB data."""

from scripts.audit_as_safety_source_link_development import audit


def test_exposed_gold_span_candidate_misses_required_current_protection():
    """A safe-looking abstention count must not hide delayed real hazards."""
    result = audit()
    assert result["denominator"] == 22
    assert (result["gold_current"], result["gold_other"]) == (16, 6)
    assert (result["current_correct"], result["other_correct"]) == (5, 1)
    assert result["abstentions"] == 16
    assert (result["observed_current"], result["observed_current_direct"]) == (13, 5)
