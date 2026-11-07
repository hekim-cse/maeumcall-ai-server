"""A/S safety confirmation accounting keeps three case groups separate."""

from types import SimpleNamespace

from scripts.run_nlu_safety_confirmation_pair import summarize


def test_confirmation_summary_counts_states_and_both_model_calls() -> None:
    cases = [SimpleNamespace(id=f"cf{number:02}") for number in range(1, 33)]
    rows = []
    for index, case in enumerate(cases):
        state = (
            "safety_action_required"
            if index == 0
            else "confirming_safety_status"
            if index < 20
            else "collecting_service_request"
        )
        rows.append(
            {
                "case_id": case.id,
                "conversation_state": state,
                "model_request_count": int(state == "collecting_service_request"),
                "focus_request_count": int(state == "confirming_safety_status"),
                "error_type": None,
                "graph_latency_ms": float(index + 1),
            }
        )
    summary = summarize(cases, rows)
    assert summary["confirmed_hazard"]["denominator"] == 12
    assert summary["confirmed_hazard"]["direct_safety"] == 1
    assert summary["confirmed_hazard"]["safety_confirmation"] == 11
    assert summary["ambiguous_hazard"]["safety_confirmation"] == 8
    assert summary["no_current_hazard"]["normal_collection"] == 12
    assert summary["no_current_hazard"]["extraction_requests"] == 12
    assert summary["confirmed_hazard"]["focus_requests"] == 11
