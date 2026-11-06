"""Probe the A/S graph with bounded model telemetry and no raw completion storage."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from unittest.mock import patch

from evals.structured_nlu.ai_heldout import AIHeldoutCase, AIHeldoutRequestPolicy
from llm.errors import AIResponseValidationError
from llm.structured_output import complete_validated_json
from scripts.run_ai_heldout_pair import _normalize_output, _post_completion
from services.flow.support.contracts import SERVICE_REQUEST_SPEC, SUPPORT_SERVICE_REQUEST_CONTRACT


def run_graph_case(
    case: AIHeldoutCase,
    *,
    endpoint: str,
    model_id: str,
    policy: AIHeldoutRequestPolicy,
    completion_post: Callable[
        [str, str, list[dict[str, str]], AIHeldoutRequestPolicy], str
    ] = _post_completion,
) -> dict:
    """Return final state and normalized attempts; never return prompts or raw responses."""
    if case.scenario_key != "고객센터:a/s 접수":
        raise ValueError("graph probe supports only A/S cases")
    import services.flow.service_workflow.structured as module

    attempts: list[dict] = []

    def complete_wrapper(messages, *, completion, validator, operation, max_attempts=2):
        if max_attempts != 2:
            raise ValueError("live analyzer retry policy differs from frozen request policy")

        def completion_wrapper(current_messages):
            started = time.perf_counter()
            outcome = {"latency_ms": 0.0, "raw": "", "output": None, "error_type": None}
            try:
                outcome["raw"] = completion_post(endpoint, model_id, current_messages, policy)
            finally:
                outcome["latency_ms"] = max(0.0, (time.perf_counter() - started) * 1000)
                attempts.append(outcome)
            return outcome["raw"]

        def validator_wrapper(parsed):
            outcome = attempts[-1]
            try:
                normalized = validator(parsed)
                outcome["output"] = _normalize_output(case, normalized).model_dump(mode="json")
                return normalized
            except (TypeError, ValueError) as error:
                outcome["error_type"] = type(error).__name__
                raise

        return complete_validated_json(
            messages,
            completion=completion_wrapper,
            validator=validator_wrapper,
            operation=operation,
            max_attempts=max_attempts,
        )

    state = {
        "user_message": case.user_message,
        "conversation_state": case.conversation_state,
        "intent": SERVICE_REQUEST_SPEC.intent,
        "fields": case.current_fields,
        "workflow_status": "in_progress",
        "history": [],
        "recommended_replies": [],
        "should_end_call": False,
    }
    result = None
    error_type = None
    try:
        with patch.object(module, "complete_validated_json", complete_wrapper):
            result = SUPPORT_SERVICE_REQUEST_CONTRACT.graph.invoke(state)
    except AIResponseValidationError as error:
        error_type = type(error).__name__
    normalized_attempts = []
    for attempt in attempts:
        reason = attempt["error_type"]
        if attempt["output"] is None and reason is None:
            try:
                json.loads(attempt["raw"])
            except json.JSONDecodeError:
                reason = "JSONDecodeError"
            else:
                reason = "InvalidJSONShape"
        normalized_attempts.append(
            {
                "contract_valid": attempt["output"] is not None,
                "latency_ms": round(attempt["latency_ms"], 3),
                "output": attempt["output"],
                "error_type": reason,
            }
        )
    return {
        "case_id": case.id,
        "model_request_count": len(attempts),
        "attempts": normalized_attempts,
        "conversation_state": result["conversation_state"] if result is not None else None,
        "workflow_status": result.get("workflow_status") if result is not None else None,
        "safety_status": result["fields"]["safety_status"] if result is not None else None,
        "error_type": error_type,
    }
