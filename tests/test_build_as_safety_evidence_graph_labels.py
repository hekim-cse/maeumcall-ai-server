"""Review-table compilation stays a draft until explicit user approval."""

import hashlib

import pytest

from experiments.as_safety_v2.json_contract import ValidationError
from scripts.build_as_safety_evidence_graph_labels import REVIEW, compile_labels


def test_review_table_compiles_in_es_order_without_granting_approval():
    payload = compile_labels()
    assert payload["review_status"] == "draft_pending_user_review"
    assert payload["review_sha256"] == hashlib.sha256(REVIEW.read_bytes()).hexdigest()
    assert [case["id"] for case in payload["cases"]] == [f"ES{i:02}" for i in range(1, 21)]
    assert sum(len(case["events"]) for case in payload["cases"]) == 22
    assert (
        sum(
            event["event_subject_kind"] is not None
            for case in payload["cases"]
            for event in case["events"]
        )
        == 19
    )
    assert payload["cases"][4]["events"][0]["target_edge_kind"] == "located_at"
    assert payload["cases"][16]["events"][0]["target_edge_kind"] == "unresolved"
    assert payload["cases"][18]["events"][0]["target_edge_kind"] is None


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("의자가 중간에 멈추는데, 방금 등받이 뒤", "원문에 없는 위험 위치"),
        ("**`located_at` 제안**", "**`distinct` 제안**"),
    ],
)
def test_compiler_rejects_unanchored_or_relation_inconsistent_review(tmp_path, old, new):
    raw = REVIEW.read_text(encoding="utf-8")
    assert old in raw
    altered = tmp_path / "review.md"
    altered.write_text(raw.replace(old, new, 1), encoding="utf-8")
    with pytest.raises((ValueError, ValidationError)):
        compile_labels(review_path=altered)


def test_compiler_rejects_duplicate_event_row(tmp_path):
    raw = REVIEW.read_text(encoding="utf-8")
    first_row = next(line for line in raw.splitlines() if line.startswith("| ES01 |"))
    altered = tmp_path / "review.md"
    altered.write_text(raw + "\n" + first_row + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate graph review row"):
        compile_labels(review_path=altered)
