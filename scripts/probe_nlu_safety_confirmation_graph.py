"""Probe both graph revisions with bounded safety-focus and extraction telemetry."""

from __future__ import annotations

import json
import time
from unittest.mock import patch

from evals.structured_nlu.ai_heldout import AIHeldoutCase, AIHeldoutRequestPolicy
from llm.errors import AIServiceError
from scripts.probe_nlu_safety_graph import run_graph_case as run_existing_graph_case
from scripts.run_ai_heldout_pair import _post_completion


def run_graph_case(
    case: AIHeldoutCase,
    *,
    endpoint: str,
    model_id: str,
    policy: AIHeldoutRequestPolicy,
) -> dict:
    """Run one A/S turn without persisting prompts or raw completions."""
    import services.flow.service_workflow.safety as safety_module

    focus_policy = policy.model_copy(update={"max_tokens": 48})
    focus_attempts: list[dict] = []

    def focus_completion(messages: list[dict[str, str]]) -> str:
        started = time.perf_counter()
        decision = None
        error_type = None
        try:
            raw = _post_completion(endpoint, model_id, messages, focus_policy)
            try:
                parsed = json.loads(raw)
                if (
                    isinstance(parsed, dict)
                    and set(parsed) == {"current_safety_issue"}
                    and isinstance(parsed["current_safety_issue"], bool)
                ):
                    decision = parsed["current_safety_issue"]
                else:
                    error_type = "InvalidDecisionShape"
            except json.JSONDecodeError:
                error_type = "JSONDecodeError"
            return raw
        except (AIServiceError, OSError, TimeoutError, ValueError) as error:
            error_type = type(error).__name__
            raise
        finally:
            focus_attempts.append(
                {
                    "decision": decision,
                    "error_type": error_type,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                }
            )

    started = time.perf_counter()
    with patch.object(safety_module, "complete_hf_safety_json", focus_completion, create=True):
        result = run_existing_graph_case(
            case,
            endpoint=endpoint,
            model_id=model_id,
            policy=policy,
        )
    result["focus_request_count"] = len(focus_attempts)
    result["focus_attempts"] = focus_attempts
    result["graph_latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return result
