"""Pin the exposed-case safety guard boundary without claiming model accuracy."""

from scripts.audit_as_safety_pre_model_guard import audit


def test_guard_forces_three_reviewed_other_source_cases_into_safety():
    """Report the false direct routes that motivate the next candidate."""
    result = audit()
    assert result["cases"] == 32
    assert result["other_observed_total"] == 6
    assert result["other_observed_forced"] == 3
    assert result["false_direct_ids"] == ["RE09", "RE11", "V02"]
    assert result["current_observed_total"] == 12
    assert result["current_observed_forced"] == 2
    assert result["unmatched_route_unmeasured"] is True
