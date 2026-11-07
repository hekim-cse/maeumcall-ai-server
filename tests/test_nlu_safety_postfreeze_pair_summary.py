"""A safety stress result counts graph routes independently from model calls."""

from types import SimpleNamespace

from scripts.run_nlu_safety_postfreeze_pair import summarize


def test_postfreeze_summary_keeps_fixed_positive_and_negative_denominators() -> None:
    """A bypass is a graph result, not a validated model attempt."""
    cases = [SimpleNamespace(id=f"pf{number:02}") for number in range(1, 17)]
    rows = []
    for index, case in enumerate(cases):
        bypass = index < 4
        rows.append(
            {
                "case_id": case.id,
                "conversation_state": "safety_action_required"
                if bypass
                else "collecting_service_request",
                "model_request_count": 0 if bypass else 1,
                "error_type": None,
            }
        )
    result = summarize(cases, rows)
    assert result["safety_positive"] == {
        "denominator": 8,
        "entered_safety_state": 4,
        "model_requests": 4,
        "zero_request_bypasses": 4,
        "graph_errors": 0,
    }
    assert result["safety_negative"]["denominator"] == 8
    assert result["safety_negative"]["incorrectly_entered_safety_state"] == 0
    rows[8]["conversation_state"] = "safety_action_required"
    rows[8]["model_request_count"] = 0
    assert summarize(cases, rows)["safety_negative"]["incorrectly_entered_safety_state"] == 1
