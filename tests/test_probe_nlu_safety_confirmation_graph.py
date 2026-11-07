"""Focused safety probe records bounded decisions and no model text."""

from types import SimpleNamespace

from scripts import probe_nlu_safety_confirmation_graph as probe


def test_focus_probe_records_attempts_without_raw_response(monkeypatch) -> None:
    responses = iter(["not json", '{"current_safety_issue": true}'])
    monkeypatch.setattr(probe, "_post_completion", lambda *args: next(responses))

    def graph_case(case, **kwargs):
        import services.flow.service_workflow.safety as safety_module

        safety_module.complete_hf_safety_json([])
        safety_module.complete_hf_safety_json([])
        return {"case_id": case.id, "attempts": [], "model_request_count": 0}

    monkeypatch.setattr(probe, "run_existing_graph_case", graph_case)
    case = SimpleNamespace(id="cf01", user_message="불꽃이 보입니다")
    policy = SimpleNamespace(model_copy=lambda update: SimpleNamespace(max_tokens=48))
    result = probe.run_graph_case(
        case,
        endpoint="http://127.0.0.1:18081/v1/chat/completions",
        model_id="/models/kanana.gguf",
        policy=policy,
    )
    assert result["focus_request_count"] == 2
    assert [attempt["decision"] for attempt in result["focus_attempts"]] == [None, True]
    assert all(
        set(attempt) == {"decision", "error_type", "latency_ms"}
        for attempt in result["focus_attempts"]
    )
    assert "not json" not in str(result)
