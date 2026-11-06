"""Every detailed NLU graph applies the shared scope decision before extraction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.structured_nlu.ai_heldout import AIHeldoutCase, AIHeldoutRequestPolicy
from llm.structured_output import SCOPE_BOUNDARY_GUIDANCE
from scripts.run_ai_heldout_pair import _run_case

REVIEWED = (
    Path(__file__).resolve().parents[1]
    / "evals/structured_nlu/data/ai_heldout/ai-heldout-reviewed.v1.json"
)
_cases = [AIHeldoutCase.model_validate(case) for case in json.loads(REVIEWED.read_text())["cases"]]
CASES = tuple(case for case in _cases if "hard_negative" in case.tags)
POLICY = AIHeldoutRequestPolicy.model_validate_json(
    REVIEWED.parent.joinpath("q4-q5-request-policy.v1.json").read_bytes()
)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_scope_boundary_instruction_reaches_each_live_analyzer(case: AIHeldoutCase) -> None:
    observed_messages: list[list[dict[str, str]]] = []

    def capture(_endpoint, _model_id, messages, _policy):
        observed_messages.append(messages)
        return "{}"

    _run_case(
        case,
        endpoint="http://127.0.0.1:18080/v1/chat/completions",
        model_id="offline-test",
        policy=POLICY,
        completion_post=capture,
    )

    assert observed_messages
    assert all(SCOPE_BOUNDARY_GUIDANCE in messages[0]["content"] for messages in observed_messages)
