"""Check fixed-pair provenance and fail-closed response boundaries."""

import copy
import json

import pytest
from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v10 import probe
from experiments.as_safety_atomic_edges_v12.pair_contract import (
    fixed_pair,
    messages,
    schema,
    validate_response,
)
from experiments.as_safety_v2.json_contract import ValidationError


def test_gold_label_changes_do_not_change_pair_request():
    case = probe.cases()["PC01"]
    changed = copy.deepcopy(case)
    changed["gold_subject_span"] = None
    changed["gold_kind"] = "unresolved"
    kiwi = Kiwi()
    pair = fixed_pair(case, "P014", kiwi)
    altered = fixed_pair(changed, "P014", kiwi)
    assert pair == altered
    assert messages(pair) == messages(altered)
    assert schema(pair) == schema(altered)
    assert "gold" not in json.dumps(messages(pair))


def test_pair_is_bound_to_one_offered_source_candidate():
    case = probe.cases()["PC01"]
    pair = fixed_pair(case, "P014", Kiwi())
    assert pair.candidate.quote == "선풍기 모터"
    assert "P014" in messages(pair)[1]["content"]
    with pytest.raises(ValueError, match="not offered"):
        fixed_pair(case, "P999", Kiwi())


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"relation_status":"supported","evidence_clause_index":2}', "supported"),
        ('{"relation_status":"unsupported","evidence_clause_index":2}', "unsupported"),
        ('{"relation_status":"insufficient","evidence_clause_index":null}', "insufficient"),
    ],
)
def test_response_contract_accepts_three_distinct_decisions(raw, expected):
    pair = fixed_pair(probe.cases()["PC01"], "P014", Kiwi())
    result = validate_response(raw, pair)
    assert result["candidate_id"] == "P014"
    assert result["relation_status"] == expected


@pytest.mark.parametrize(
    "raw",
    [
        '{"relation_status":"supported","evidence_clause_index":null}',
        '{"relation_status":"unsupported","evidence_clause_index":0}',
        '{"relation_status":"supported","evidence_clause_index":true}',
        '{"relation_status":"supported","evidence_clause_index":2,"extra":1}',
        '{"relation_status":"other","evidence_clause_index":2}',
        '{"relation_status":"","evidence_clause_index":2}',
        '{"relation_status":" ","evidence_clause_index":2}',
        '{"relation_status":" supported ","evidence_clause_index":2}',
        '{"relation_status":"supported","evidence_clause_index":2,"relation_status":"unsupported"}',
    ],
)
def test_response_contract_rejects_inconsistent_or_unanchored_outputs(raw):
    pair = fixed_pair(probe.cases()["PC01"], "P014", Kiwi())
    with pytest.raises(ValidationError):
        validate_response(raw, pair)
