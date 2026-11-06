"""Safety routing and model contract counts have distinct denominators."""

from types import SimpleNamespace

from scripts.run_nlu_safety_graph_pair import _summarize


def test_summary_counts_graph_routes_and_model_attempts_separately() -> None:
    cases = [SimpleNamespace(id=f"case-{number:02}") for number in range(1, 21)]
    results = []
    for number, case in enumerate(cases, start=1):
        bypass = number <= 8
        scope = number >= 17
        results.append(
            {
                "case_id": case.id,
                "conversation_state": "safety_action_required"
                if bypass
                else "collecting_service_request",
                "model_request_count": 0 if bypass else 1,
                "attempts": []
                if bypass
                else [
                    {
                        "contract_valid": True,
                        "output": {"user_action": "unknown" if scope else "provide_details"},
                    }
                ],
            }
        )

    summary = _summarize(cases, results)
    assert summary["safety_positive"] == {
        "denominator": 8,
        "entered_safety_state": 8,
        "model_requests": 0,
    }
    assert summary["safety_negative"]["incorrectly_entered_safety_state"] == 0
    assert summary["out_of_scope"]["contract_pass"] == 4
    assert summary["out_of_scope"]["unknown_action"] == 4


def test_scope_summary_uses_final_retry_result() -> None:
    cases = [SimpleNamespace(id=f"case-{number:02}") for number in range(1, 21)]
    results = [
        {
            "case_id": case.id,
            "conversation_state": "collecting_service_request",
            "model_request_count": 1,
            "attempts": [{"contract_valid": True, "output": {"user_action": "unknown"}}],
        }
        for case in cases
    ]
    failure = {"contract_valid": False, "output": None}
    results[16]["attempts"] = [
        failure,
        {"contract_valid": True, "output": {"user_action": "unknown"}},
    ]
    results[16]["model_request_count"] = 2
    results[19]["attempts"] = [failure, failure]
    results[19]["model_request_count"] = 2

    scope = _summarize(cases, results)["out_of_scope"]
    assert scope == {
        "denominator": 4,
        "contract_pass": 3,
        "unknown_action": 3,
        "model_requests": 6,
    }
