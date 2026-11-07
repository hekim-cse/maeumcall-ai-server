"""Owner-reviewed CX cases are development regressions, never heldout scores."""

import re
from pathlib import Path

import pytest

from services.flow.service_workflow.safety import has_explicit_safety_issue

REVIEW = Path("docs/portfolio/nlu_safety_context_fresh_review.md")


def _cx_messages() -> dict[str, str]:
    """Read the accepted development utterances from their review table."""
    rows: dict[str, str] = {}
    for line in REVIEW.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if cells and re.fullmatch(r"CX\d{2}", cells[0]):
            rows[cells[0]] = cells[2]
    if set(rows) != {f"CX{number:02}" for number in range(1, 17)}:
        raise ValueError("review table must contain CX01–CX16 exactly once")
    return rows


@pytest.mark.parametrize("case_number", range(1, 17))
def test_accepted_cx_safety_boundary(case_number: int) -> None:
    """Retain the accepted affirmative versus non-affirmative distinctions."""
    message = _cx_messages()[f"CX{case_number:02}"]
    assert has_explicit_safety_issue(message) is (case_number <= 8)
