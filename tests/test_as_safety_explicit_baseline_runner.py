"""Exercise safe routing when a development-only prediction fails."""

from pathlib import Path

from scripts import run_as_safety_explicit_baseline_v1 as runner


def _without_protocol_io(monkeypatch):
    monkeypatch.setattr(
        runner,
        "_checked_protocol",
        lambda _path: (
            {"frozen_code_commit": "frozen", "claim_scope": "development_only"},
            "protocol",
            runner._cases(),
        ),
    )


def test_unexpected_prediction_error_abstains_without_retry(monkeypatch):
    _without_protocol_io(monkeypatch)
    original = runner.predict_relation
    calls = 0

    def fail_first(message, **kwargs):
        nonlocal calls
        if kwargs["hazard_owner_span"] == {"clause_index": 2, "quote": "로봇청소기 전원 연결부"}:
            calls += 1
            raise RuntimeError("private source must not appear in output")
        return original(message, **kwargs)

    monkeypatch.setattr(runner, "predict_relation", fail_first)
    result = runner.evaluate(Path("not-read"))
    assert calls == 1
    assert result["routes"]["ES01"] == "confirming_safety_status"
    assert result["summary"]["errors"] == 1
    first = result["events"][0]
    assert first["predicted_relation"] == "unknown"
    assert first["error_code"] == "unexpected_exception"
    assert "private source" not in str(result)


def test_confirmed_current_event_keeps_safety_priority_after_peer_error(monkeypatch):
    _without_protocol_io(monkeypatch)
    original = runner.predict_relation

    def fail_other_event(message, **kwargs):
        owner = kwargs["hazard_owner_span"]
        if owner is not None and owner["quote"] == "다른 기기의 충전기":
            raise RuntimeError("peer error")
        if owner is not None and owner["quote"] == "프린터 옆면":
            return {"relation": "current", "basis": "test_confirmed_current"}
        return original(message, **kwargs)

    monkeypatch.setattr(runner, "predict_relation", fail_other_event)
    result = runner.evaluate(Path("not-read"))
    assert result["routes"]["ES06"] == "safety_action_required"
    assert result["summary"]["errors"] == 1
