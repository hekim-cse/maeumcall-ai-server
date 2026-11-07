"""Clause IDs bind model evidence to source text without copied phrases."""

import pytest

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
