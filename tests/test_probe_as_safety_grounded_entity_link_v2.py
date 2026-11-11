"""Boundary checks for v1 grounded-link fallback attribution."""

from __future__ import annotations

import json

import pytest

from scripts.probe_as_safety_grounded_entity_link_v2 import (
    ANCHOR_STATUSES,
    assess_grounded_entity_link,
)

MESSAGE = "접수할 노트북이 작동하지 않습니다. 친구 태블릿의 충전기에서 연기가 납니다."
ANCHORS = {
    "target_mention": "노트북",
    "product_index": 1,
    "owner_mention": "친구 태블릿의 충전기",
    "owner_clause_index": 2,
}
TARGET = {"clause_index": 1, "quote": "접수할 노트북"}
OWNER = {"clause_index": 2, "quote": "친구 태블릿의 충전기"}


def _decision(link: str, evidence: list[dict]) -> str:
    return json.dumps({"entity_link": link, "evidence": evidence}, ensure_ascii=False)


def _assess(raw: str) -> dict:
    return assess_grounded_entity_link(raw, MESSAGE, **ANCHORS)


@pytest.mark.parametrize("link", ["same_or_part", "distinct_item"])
def test_anchored_decisions_keep_raw_link_without_claiming_semantic_truth(link):
    result = _assess(_decision(link, [TARGET, OWNER]))
    assert result == {
        "raw_link": link,
        "anchor_status": "accepted",
        "effective_link": link,
        "evidence": [TARGET, OWNER],
    }


def test_model_abstention_is_not_counted_as_anchor_rejection():
    assert _assess(_decision("unresolved", [])) == {
        "raw_link": "unresolved",
        "anchor_status": "model_abstained",
        "effective_link": "unresolved",
        "evidence": [],
    }


@pytest.mark.parametrize(
    ("evidence", "status"),
    [
        ([], "rejected_missing_evidence"),
        ([TARGET, {"clause_index": 2, "quote": "없는 인용"}], "rejected_invalid_quote"),
        ([OWNER], "rejected_missing_target"),
        ([TARGET], "rejected_missing_owner"),
    ],
)
def test_fallback_reason_is_separate_from_raw_model_choice(evidence, status):
    result = _assess(_decision("distinct_item", evidence))
    assert result == {
        "raw_link": "distinct_item",
        "anchor_status": status,
        "effective_link": "unresolved",
        "evidence": [],
    }


def test_invalid_quote_takes_priority_over_missing_mention():
    result = _assess(_decision("same_or_part", [{"clause_index": 3, "quote": "없음"}]))
    assert result["anchor_status"] == "rejected_invalid_quote"
    assert result["effective_link"] == "unresolved"


def test_same_clause_one_quote_can_cover_both_mentions():
    message = "제 노트북의 배터리에서 냄새가 납니다."
    evidence = [{"clause_index": 1, "quote": "제 노트북의 배터리"}]
    result = assess_grounded_entity_link(
        _decision("same_or_part", evidence),
        message,
        target_mention="노트북",
        product_index=1,
        owner_mention="배터리",
        owner_clause_index=1,
    )
    assert result["anchor_status"] == "accepted"
    assert result["evidence"] == evidence


@pytest.mark.parametrize(
    "raw",
    [
        '{"entity_link":"distinct_item","entity_link":"same_or_part","evidence":[]}',
        '{"entity_link":"distinct_item","evidence":NaN}',
        '{"entity_link":"distinct_item","evidence":[{"clause_index":true,"quote":"노트북"}]}',
        '{"entity_link":"distinct_item","evidence":[],"extra":1}',
        _decision("unsupported", []),
        _decision("unresolved", [TARGET]),
        "{",
    ],
)
def test_v1_contract_errors_are_not_reclassified_as_anchor_rejection(raw):
    with pytest.raises((ValueError, json.JSONDecodeError)):
        _assess(raw)


def test_all_anchor_statuses_have_a_regression_case():
    assert ANCHOR_STATUSES == {
        "model_abstained",
        "accepted",
        "rejected_missing_evidence",
        "rejected_invalid_quote",
        "rejected_missing_target",
        "rejected_missing_owner",
    }
