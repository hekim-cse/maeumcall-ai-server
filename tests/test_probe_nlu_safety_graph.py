"""The graph probe distinguishes a safety bypass from model validation."""

import json
from pathlib import Path

from evals.structured_nlu.ai_heldout import AIHeldoutCase, AIHeldoutRequestPolicy
from scripts.probe_nlu_safety_graph import run_graph_case
from services.flow.support.contracts import SERVICE_REQUEST_SPEC

DATA = Path("evals/structured_nlu/data/ai_heldout")


def _case(suffix: str) -> AIHeldoutCase:
    cases = json.loads((DATA / "nlu-review-followup-reviewed.v1.json").read_text())["cases"]
    return AIHeldoutCase.model_validate(next(case for case in cases if case["id"].endswith(suffix)))


def _policy() -> AIHeldoutRequestPolicy:
    return AIHeldoutRequestPolicy.model_validate_json(
        (DATA / "q4-q5-request-policy.v1.json").read_bytes()
    )


def test_explicit_hazard_bypasses_model_and_enters_safety_state() -> None:
    def should_not_call_model(*args, **kwargs):
        raise AssertionError("safety guard must bypass the model")

    result = run_graph_case(
        _case("rf01"),
        endpoint="http://127.0.0.1:18081/v1/chat/completions",
        model_id="/models/kanana.gguf",
        policy=_policy(),
        completion_post=should_not_call_model,
    )
    assert result["model_request_count"] == 0
    assert result["attempts"] == []
    assert result["conversation_state"] == "safety_action_required"
    assert result["safety_status"] == "safety_issue"


def test_empty_detail_response_becomes_unknown_with_one_valid_model_attempt() -> None:
    def empty_detail(*args, **kwargs):
        return json.dumps(
            {
                "intent": SERVICE_REQUEST_SPEC.intent,
                "fields": {key: None for key in SERVICE_REQUEST_SPEC.field_keys},
                "user_action": "provide_details",
                "change_field": None,
            }
        )

    result = run_graph_case(
        _case("rf02"),
        endpoint="http://127.0.0.1:18081/v1/chat/completions",
        model_id="/models/kanana.gguf",
        policy=_policy(),
        completion_post=empty_detail,
    )
    assert result["model_request_count"] == 1
    assert result["attempts"][0]["contract_valid"]
    assert result["attempts"][0]["output"]["user_action"] == "unknown"
    assert result["conversation_state"] != "safety_action_required"
    assert result["safety_status"] is None
