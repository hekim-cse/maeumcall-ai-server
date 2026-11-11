"""Contract checks for the development-only hazard owner evidence probe."""

import json

import pytest

from scripts.probe_as_safety_owner_evidence import (
    owner_evidence_messages,
    owner_evidence_schema,
    validate_owner_evidence,
)

UTTERANCE = "공기청정기를 맡기려고 합니다. 가습기의 전원선에서 연기가 났습니다."
CURRENT_UTTERANCE = "공기청정기를 맡기려고 합니다. 공기청정기 전원선에서 연기가 났습니다."


def test_messages_preserve_whole_utterance_and_reviewed_spans_without_gold() -> None:
    """The model sees the oracle inputs but not the expected source identity."""
    messages = owner_evidence_messages(
        UTTERANCE,
        product_index=1,
        hazard_index=2,
        event_status="observed",
        target_mention="공기청정기",
        hazard_event_mention="가습기의 전원선에서 연기가 났습니다",
    )
    prompt = messages[1]["content"]
    assert UTTERANCE in prompt
    assert "검수된 접수 대상 구절: 공기청정기" in prompt
    assert "검수된 위험 사건 구절: 가습기의 전원선에서 연기가 났습니다" in prompt
    assert "expected_relation" not in prompt
    assert "gold_relation" not in prompt


@pytest.mark.parametrize("clause_count", [0, -1, True, 1.0])
def test_schema_rejects_invalid_clause_count(clause_count: object) -> None:
    """Only a positive number of real source clauses can be indexed."""
    with pytest.raises(ValueError, match="source clause"):
        owner_evidence_schema(clause_count)


def test_schema_closes_keys_and_indices() -> None:
    """Generation choices have finite IDs and relation categories."""
    schema = owner_evidence_schema(2)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["source_clause_index"]["enum"] == [None, 1, 2]
    assert schema["properties"]["source_relation"]["enum"] == [
        "current",
        "other",
        "unknown",
    ]


@pytest.mark.parametrize(
    ("product_index", "hazard_index", "event_status", "target", "hazard"),
    [
        (0, 2, "observed", "공기청정기", "연기가 났습니다"),
        (True, 2, "observed", "공기청정기", "연기가 났습니다"),
        (1, 3, "observed", "공기청정기", "연기가 났습니다"),
        (1, 2, "nonoccurring", "공기청정기", "연기가 났습니다"),
        (1, 2, "observed", " ", "연기가 났습니다"),
        (1, 2, "observed", "가습기", "연기가 났습니다"),
        (1, 2, "observed", "공기청정기", "공기청정기"),
    ],
)
def test_messages_reject_invalid_reviewed_inputs(
    product_index: object,
    hazard_index: object,
    event_status: str,
    target: str,
    hazard: str,
) -> None:
    """Wrong oracle anchors cannot silently enter a model request."""
    with pytest.raises(ValueError):
        owner_evidence_messages(
            UTTERANCE,
            product_index=product_index,
            hazard_index=hazard_index,
            event_status=event_status,
            target_mention=target,
            hazard_event_mention=hazard,
        )


@pytest.mark.parametrize(
    ("decision", "utterance"),
    [
        (
            {
                "source_mention": "가습기",
                "source_clause_index": 2,
                "link_kind": "explicit_other",
                "source_relation": "other",
            },
            UTTERANCE,
        ),
        (
            {
                "source_mention": "공기청정기",
                "source_clause_index": 2,
                "link_kind": "same_entity",
                "source_relation": "current",
            },
            CURRENT_UTTERANCE,
        ),
        (
            {
                "source_mention": "전원선",
                "source_clause_index": 2,
                "link_kind": "part_or_anaphora",
                "source_relation": "current",
            },
            CURRENT_UTTERANCE,
        ),
        (
            {
                "source_mention": None,
                "source_clause_index": None,
                "link_kind": "unresolved",
                "source_relation": "unknown",
            },
            UTTERANCE,
        ),
    ],
)
def test_valid_decisions_require_source_or_explicit_abstention(
    decision: dict, utterance: str
) -> None:
    """Valid output keeps an auditable span or an explicit abstention."""
    assert validate_owner_evidence(json.dumps(decision), utterance) == decision


@pytest.mark.parametrize(
    "change",
    [
        {"source_mention": " "},
        {"source_mention": None},
        {"source_mention": "없는 제품"},
        {"source_clause_index": None},
        {"source_clause_index": 1},
        {"source_clause_index": True},
        {"source_clause_index": 3},
        {"source_relation": "current"},
        {"link_kind": "unresolved"},
        {"link_kind": "other"},
        {"unexpected": 1},
    ],
)
def test_invalid_source_or_contradictory_relation_rejected(change: dict) -> None:
    """Evidence must be in its clause and agree with the finite link code."""
    decision = {
        "source_mention": "가습기",
        "source_clause_index": 2,
        "link_kind": "explicit_other",
        "source_relation": "other",
    }
    decision.update(change)
    with pytest.raises(ValueError):
        validate_owner_evidence(json.dumps(decision), UTTERANCE)


def test_unresolved_requires_both_evidence_fields_null() -> None:
    """An ambiguous source cannot carry a selected owner as hidden evidence."""
    decision = {
        "source_mention": "가습기",
        "source_clause_index": 2,
        "link_kind": "unresolved",
        "source_relation": "unknown",
    }
    with pytest.raises(ValueError, match="null source evidence"):
        validate_owner_evidence(json.dumps(decision), UTTERANCE)


def test_duplicate_json_key_rejected() -> None:
    """Later duplicate fields cannot override an earlier relation decision."""
    raw = (
        '{"source_mention":null,"source_clause_index":null,'
        '"link_kind":"unresolved","source_relation":"unknown",'
        '"source_relation":"current"}'
    )
    with pytest.raises(ValueError, match="duplicate JSON keys"):
        validate_owner_evidence(raw, UTTERANCE)
