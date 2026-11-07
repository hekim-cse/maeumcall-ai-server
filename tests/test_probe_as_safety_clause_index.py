"""Clause IDs bind model evidence to source text without copied phrases."""

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from evals.structured_nlu.ai_heldout import AIHeldoutDataset
from scripts.probe_as_safety_clause_index import (
    evidence_schema,
    split_clauses,
    validate_indexed_evidence,
)
from scripts.probe_as_safety_evidence import route_evidence


def test_source_clause_ids_preserve_other_product_context() -> None:
    clauses = split_clauses(
        "방에 둔 방향제에서 타는 냄새가 나요. A/S를 문의하는 공기청정기는 화면만 꺼집니다."
    )
    assert len(clauses) == 2
    assert clauses[0].startswith("방에 둔 방향제")
    assert evidence_schema(len(clauses))["properties"]["evidence_index"]["enum"] == [
        None,
        1,
        2,
    ]
    decision = validate_indexed_evidence(
        '{"evidence_index":1,"target":"other","assertion":"observed"}', 2
    )
    assert route_evidence(decision) == "collecting_service_request"


@pytest.mark.parametrize(
    "raw",
    [
        '{"evidence_index":3,"target":"current","assertion":"observed"}',
        '{"evidence_index":true,"target":"current","assertion":"observed"}',
        '{"evidence_index":null,"target":"current","assertion":"none"}',
    ],
)
def test_invalid_or_contradictory_clause_id_is_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        validate_indexed_evidence(raw, 2)


def test_exposed_development_results_have_fixed_order_and_bounded_fields() -> None:
    root = Path("evals/structured_nlu/data/ai_heldout")
    dataset_path = root / "nlu-safety-confirmation-reviewed.v1.json"
    dataset = AIHeldoutDataset.model_validate_json(dataset_path.read_bytes())
    expected_ids = [case.id for case in dataset.cases]
    digest = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    results = [
        json.loads((root / name).read_text(encoding="utf-8"))
        for name in (
            "nlu-safety-evidence-exposed-development.v1.json",
            "nlu-safety-evidence-exposed-development.v2.json",
            "nlu-safety-clause-index-exposed-development.v1.json",
        )
    ]
    for result in results:
        assert result["claim_scope"] == "already_exposed_ai_authored_32_case_diagnostic_only"
        assert result["dataset_sha256"] == digest
        assert [row["case_id"] for row in result["rows"]] == expected_ids
        assert all("user_message" not in row and "raw" not in row for row in result["rows"])
    assert Counter(row["error_type"] for row in results[0]["rows"]) == {"JSONDecodeError": 32}
    assert sum(row["route"] is not None for row in results[1]["rows"]) == 10
    indexed = results[2]["rows"]
    assert all(row["error_type"] is None for row in indexed)
    assert [
        Counter(row["route"] for row in indexed[start:stop])
        for start, stop in ((0, 12), (12, 20), (20, 32))
    ] == [
        Counter({"safety_action_required": 10, "collecting_service_request": 2}),
        Counter(
            {
                "safety_action_required": 2,
                "confirming_safety_status": 4,
                "collecting_service_request": 2,
            }
        ),
        Counter(
            {
                "safety_action_required": 6,
                "confirming_safety_status": 1,
                "collecting_service_request": 5,
            }
        ),
    ]
