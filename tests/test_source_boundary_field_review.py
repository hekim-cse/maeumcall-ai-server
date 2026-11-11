"""Check proposed GB evidence anchors before human review and model exposure."""

import json
import re
from pathlib import Path

from scripts.probe_as_safety_clause_index import split_clauses
from scripts.probe_as_safety_relation import route_relation, validate_relation

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "docs/portfolio/nlu_safety_source_boundary_fresh_review.md"
FIELDS = ROOT / "docs/portfolio/nlu_safety_source_boundary_field_review.md"
DATA = ROOT / "evals/structured_nlu/data/ai_heldout/as-safety-source-boundary-reviewed.v1.json"
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


def test_adopted_data_matches_review_and_route_contract():
    """Reject a dataset drift from the user-approved utterances or route rules."""
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    assert payload["provenance"] == "ai_authored"
    assert payload["review_status"] == "owner_approved_for_exploration"
    assert payload["model_exposure_at_freeze"] == "none"
    utterances = _rows(REVIEW)
    assert [case["id"] for case in payload["cases"]] == [f"GB{i:02}" for i in range(1, 25)]
    for case in payload["cases"]:
        assert case["user_message"] == utterances[case["id"]][1]
        clauses = split_clauses(case["user_message"])
        decision = validate_relation(json.dumps(case["expected_relation"]), len(clauses))
        assert route_relation(decision) == case["expected_route"]
        spans = case["reviewed_spans"]
        for index_key, quote_key in (
            ("product_index", "target_mention"),
            ("hazard_index", "hazard_event_mention"),
        ):
            index, quote = decision[index_key], spans[quote_key]
            assert (index is None) == (quote is None)
            if index is not None:
                assert clauses[index - 1].count(quote) == 1
        owner_index, owner_quote = spans["owner_clause_index"], spans["owner_mention"]
        assert (owner_index is None) == (owner_quote is None)
        if owner_index is not None:
            assert clauses[owner_index - 1].count(owner_quote) == 1
