"""Check proposed GB evidence anchors before human review and model exposure."""

import re
from pathlib import Path

from scripts.probe_as_safety_clause_index import split_clauses

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "docs/portfolio/nlu_safety_source_boundary_fresh_review.md"
FIELDS = ROOT / "docs/portfolio/nlu_safety_source_boundary_field_review.md"
ANCHOR = re.compile(r"^(\d+) `([^`]+)`$")


def _rows(path: Path) -> dict[str, list[str]]:
    """Read only the numbered GB table rows from a review document."""
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("| GB"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells[0] in result:
                raise ValueError("duplicate GB ID")
            result[cells[0]] = cells
    return result


def test_all_proposed_quotes_anchor_once_in_reviewed_sentence():
    """Catch quote and clause-index drift while the gold table is still a draft."""
    utterances = _rows(REVIEW)
    fields = _rows(FIELDS)
    expected = {f"GB{i:02}" for i in range(1, 25)}
    assert set(utterances) == set(fields) == expected
    for case_id in sorted(expected):
        clauses = split_clauses(utterances[case_id][1])
        row = fields[case_id]
        assert len(row) == 6
        for cell in row[1:4]:
            if cell == "공란":
                continue
            match = ANCHOR.fullmatch(cell)
            assert match is not None, (case_id, cell)
            index, mention = int(match[1]), match[2]
            assert 1 <= index <= len(clauses), (case_id, cell)
            assert clauses[index - 1].count(mention) == 1, (case_id, cell)
    for case_id in ("GB21", "GB24"):
        assert fields[case_id][1:4] == ["공란"] * 3
        assert fields[case_id][4] == "`none / none`"
