"""Keep already exposed SC findings as development regressions, not new scores."""

import json
from pathlib import Path

import pytest

from services.flow.service_workflow.safety import has_explicit_safety_issue

SC_PATH = Path("evals/structured_nlu/data/ai_heldout/nlu-safety-contract-reviewed.v1.json")


@pytest.mark.parametrize("case_number", range(1, 17))
def test_reviewed_sc_safety_boundary(case_number: int) -> None:
    """Protect both the four observed misses and eight non-hazard controls."""
    cases = json.loads(SC_PATH.read_text(encoding="utf-8"))["cases"]
    case = cases[case_number - 1]
    assert case["id"] == f"nlu-safety-contract-sc{case_number:02}"
    assert has_explicit_safety_issue(case["user_message"]) is (case_number <= 8)
