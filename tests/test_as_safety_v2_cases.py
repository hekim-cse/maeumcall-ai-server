"""Check source and annotation boundaries of the v2 development set."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.as_safety_v2.cases import CASE_IDS, load_development_cases

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
PATHS = {
    "re_dataset": DATA / "as-safety-relation-fresh-reviewed.v1.json",
    "v_dataset": DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
    "labels_path": DATA / "as-safety-extraction-v2-development-labels.v1.json",
    "spans_path": DATA / "as-safety-oracle-relation-spans-reviewed.v1.json",
    "subject_path": DATA / "as-safety-owner-evidence-reviewed.v1.json",
    "owner_review_path": ROOT / "docs/portfolio/nlu_safety_owner_resolution_review.md",
}


def test_loads_only_approved_development_references():
    cases = load_development_cases(**PATHS)
    assert tuple(case["id"] for case in cases) == CASE_IDS
    by_id = {case["id"]: case for case in cases}
    assert by_id["RE02"]["owner_reference"] == {"clause_index": 2, "quote": "그 제품"}
    assert by_id["RE02"]["owner_referent"] == {"clause_index": 1, "quote": "공기순환기"}
    assert by_id["V04"]["relation"] == "current"
    assert by_id["V07"]["subject_reference"] == {"clause_index": 1, "quote": "바닥"}
    assert by_id["V07"]["subject_interpretation"] == "믹서기 바닥"


@pytest.mark.parametrize("mutation", ["utterance_hash", "owner_quote", "case_order"])
def test_rejects_mutated_development_reference(tmp_path: Path, mutation: str):
    labels = json.loads(PATHS["labels_path"].read_text(encoding="utf-8"))
    if mutation == "utterance_hash":
        labels["cases"][0]["utterance_sha256"] = "0" * 64
    elif mutation == "owner_quote":
        labels["cases"][0]["owner_reference"]["quote"] = "없는 물건"
    else:
        labels["cases"][0], labels["cases"][1] = labels["cases"][1], labels["cases"][0]
    tampered = tmp_path / "labels.json"
    tampered.write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        load_development_cases(**{**PATHS, "labels_path": tampered})
