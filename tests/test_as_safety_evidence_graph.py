"""Contract tests for development-only event, subject, and target edges."""

import json

import pytest

from experiments.as_safety_v2.evidence_graph import (
    aggregate_event_routes,
    decide_with_contract_fallback,
    evidence_graph_messages,
    evidence_graph_schema,
    route_for,
    validate_evidence_graph,
)
from experiments.as_safety_v2.json_contract import ValidationError

MESSAGE = (
    "접수할 전기포트가 고장 났습니다. 전기포트 전원선에서 연기가 났어요. 옆집 토스터도 고장입니다."
)
EVENT = {"clause_index": 2, "quote": "연기가 났어요"}
TARGET = {"product_index": 1, "target_mention": "전기포트"}
CURRENT = {
    "subject_span": {"clause_index": 2, "quote": "전기포트 전원선"},
    "event_subject_kind": "subject",
    "event_subject_evidence_span": {
        "clause_index": 2,
        "quote": "전기포트 전원선에서 연기가 났어요",
    },
    "target_edge_kind": "part_of",
    "target_edge_evidence_span": {"clause_index": 2, "quote": "전기포트 전원선"},
}


def _validate(payload, *, occurrence="observed", message=MESSAGE, event=EVENT):
    return validate_evidence_graph(
        json.dumps(payload, ensure_ascii=False),
        message,
        event,
        occurrence,
        **TARGET,
    )


def test_prompt_shows_oracle_event_and_target_but_no_reviewed_relation_or_route():
    messages = evidence_graph_messages(MESSAGE, EVENT, "observed", **TARGET)
    prompt = "\n".join(item["content"] for item in messages)
    assert "검수된 위험 사건 E: 2. 연기가 났어요" in prompt
    assert "접수 제품 A: 1. 전기포트" in prompt
    assert "effective_relation" not in prompt
    assert "safety_action_required" not in prompt
    schema = evidence_graph_schema(MESSAGE)
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == set(schema["required"])
    assert schema["properties"]["target_edge_kind"]["enum"] == [
        "coreference",
        "distinct",
        "part_of",
        "same_entity",
        "unresolved",
    ]


def test_current_edge_and_attachment_are_separately_anchored():
    result = _validate(CURRENT)
    assert result["event_subject_kind"] == "subject"
    assert result["subject_span"]["quote"] == "전기포트 전원선"
    assert result["subject_span"]["start"] == 0
    assert result["target_edge_kind"] == "part_of"
    assert result["effective_relation"] == "current"
    decision = decide_with_contract_fallback(
        json.dumps(CURRENT, ensure_ascii=False), MESSAGE, EVENT, "observed", **TARGET
    )
    assert decision["route"] == "safety_action_required"
    assert decision["error_code"] is None


def test_distinct_edge_routes_to_general_service_and_uncertain_current_to_confirmation():
    message = "접수할 전기포트가 고장 났습니다. 옆집 토스터에서 연기가 났어요."
    other = {
        **CURRENT,
        "subject_span": {"clause_index": 2, "quote": "옆집 토스터"},
        "event_subject_evidence_span": {
            "clause_index": 2,
            "quote": "옆집 토스터에서 연기가 났어요",
        },
        "target_edge_kind": "distinct",
        "target_edge_evidence_span": {"clause_index": 2, "quote": "옆집 토스터"},
    }
    assert _validate(other, message=message)["effective_relation"] == "other"
    assert route_for("observed", "other") == "collecting_service_request"
    assert route_for("uncertain", "current") == "confirming_safety_status"


def test_unrelated_subject_sentence_cannot_be_attached_to_event():
    unrelated = {
        **CURRENT,
        "subject_span": {"clause_index": 3, "quote": "옆집 토스터"},
        "event_subject_kind": "implicit",
        "event_subject_evidence_span": {"clause_index": 3, "quote": "옆집 토스터도 고장입니다"},
        "target_edge_kind": "distinct",
        "target_edge_evidence_span": {"clause_index": 3, "quote": "옆집 토스터"},
    }
    decision = decide_with_contract_fallback(
        json.dumps(unrelated, ensure_ascii=False), MESSAGE, EVENT, "observed", **TARGET
    )
    assert decision["error_code"] == "event_attachment_unlinked"
    assert decision["route"] == "confirming_safety_status"


def test_direct_subject_must_overlap_event_local_cue_but_implicit_can_be_prior():
    wrong_direct = {
        **CURRENT,
        "subject_span": {"clause_index": 3, "quote": "옆집 토스터"},
    }
    decision = decide_with_contract_fallback(
        json.dumps(wrong_direct, ensure_ascii=False), MESSAGE, EVENT, "observed", **TARGET
    )
    assert decision["error_code"] == "subject_attachment_unlinked"
    implicit = {
        **CURRENT,
        "subject_span": {"clause_index": 1, "quote": "전기포트"},
        "event_subject_kind": "implicit",
        "target_edge_kind": "coreference",
    }
    assert _validate(implicit)["effective_relation"] == "current"


def test_distinct_cue_citing_only_target_cannot_send_observed_hazard_to_general_service():
    false_other = {
        **CURRENT,
        "target_edge_kind": "distinct",
        "target_edge_evidence_span": {"clause_index": 1, "quote": "전기포트"},
    }
    decision = decide_with_contract_fallback(
        json.dumps(false_other, ensure_ascii=False), MESSAGE, EVENT, "observed", **TARGET
    )
    assert decision["error_code"] == "distinct_subject_unlinked"
    assert decision["effective_relation"] == "unknown"
    assert decision["route"] == "confirming_safety_status"


def test_multi_event_aggregation_prioritizes_current_hazard_over_other_product():
    message = (
        "접수할 프린터가 고장 났습니다. 옆 라디오 충전기에서 불꽃이 튀었어요. "
        "프린터 전원선이 녹았어요."
    )
    target = {"product_index": 1, "target_mention": "프린터"}
    other = {
        "subject_span": {"clause_index": 2, "quote": "옆 라디오 충전기"},
        "event_subject_kind": "subject",
        "event_subject_evidence_span": {
            "clause_index": 2,
            "quote": "옆 라디오 충전기에서 불꽃이 튀었어요",
        },
        "target_edge_kind": "distinct",
        "target_edge_evidence_span": {"clause_index": 2, "quote": "옆 라디오 충전기"},
    }
    current = {
        "subject_span": {"clause_index": 3, "quote": "프린터 전원선"},
        "event_subject_kind": "subject",
        "event_subject_evidence_span": {"clause_index": 3, "quote": "프린터 전원선이 녹았어요"},
        "target_edge_kind": "part_of",
        "target_edge_evidence_span": {"clause_index": 3, "quote": "프린터 전원선"},
    }
    decisions = [
        decide_with_contract_fallback(
            json.dumps(other, ensure_ascii=False),
            message,
            {"clause_index": 2, "quote": "불꽃이 튀었어요"},
            "observed",
            **target,
        ),
        decide_with_contract_fallback(
            json.dumps(current, ensure_ascii=False),
            message,
            {"clause_index": 3, "quote": "녹았어요"},
            "observed",
            **target,
        ),
    ]
    assert [item["route"] for item in decisions] == [
        "collecting_service_request",
        "safety_action_required",
    ]
    assert aggregate_event_routes([item["route"] for item in decisions]) == "safety_action_required"
    assert (
        aggregate_event_routes(["collecting_service_request", "confirming_safety_status"])
        == "confirming_safety_status"
    )


@pytest.mark.parametrize("routes", [[], "safety_action_required", ["bad"], [None]])
def test_event_aggregation_rejects_invalid_inputs(routes):
    with pytest.raises(ValidationError):
        aggregate_event_routes(routes)


def test_unresolved_and_contract_error_fail_closed():
    unresolved = {
        "subject_span": None,
        "event_subject_kind": "unresolved",
        "event_subject_evidence_span": None,
        "target_edge_kind": "unresolved",
        "target_edge_evidence_span": None,
    }
    assert _validate(unresolved)["effective_relation"] == "unknown"
    decision = decide_with_contract_fallback(
        json.dumps(unresolved), MESSAGE, EVENT, "observed", **TARGET
    )
    assert decision["route"] == "confirming_safety_status"
    invalid = {**CURRENT, "target_edge_evidence_span": {"clause_index": 2, "quote": "없는 구절"}}
    decision = decide_with_contract_fallback(
        json.dumps(invalid, ensure_ascii=False), MESSAGE, EVENT, "observed", **TARGET
    )
    assert decision == {
        "effective_relation": "unknown",
        "route": "confirming_safety_status",
        "error_code": "quote_unanchored",
        "error_field": "target_edge_evidence_span",
    }


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"event_subject_kind": "unresolved"}, "attachment_consistency_invalid"),
        ({"subject_span": None}, "attachment_consistency_invalid"),
        ({"event_subject_evidence_span": None}, "attachment_consistency_invalid"),
        ({"target_edge_kind": "unresolved"}, "edge_consistency_invalid"),
        ({"target_edge_evidence_span": None}, "edge_consistency_invalid"),
        ({"target_edge_kind": "same"}, "edge_kind_invalid"),
        ({"event_subject_kind": "guessed"}, "attachment_kind_invalid"),
        ({"extra": "field"}, "fields_invalid"),
    ],
)
def test_invalid_edge_and_attachment_combinations_are_rejected(changes, code):
    with pytest.raises(ValidationError) as caught:
        _validate({**CURRENT, **changes})
    assert caught.value.code == code


def test_oracle_event_must_be_source_anchored_and_observed_or_uncertain():
    with pytest.raises(ValidationError, match="quote_unanchored"):
        _validate(CURRENT, event={"clause_index": 2, "quote": "불꽃이 났어요"})
    with pytest.raises(ValidationError, match="occurrence_invalid"):
        _validate(CURRENT, occurrence="nonoccurring")


def test_duplicate_json_fields_and_duplicate_quotes_fail_without_echoing_raw():
    raw = json.dumps(CURRENT, ensure_ascii=False)[:-1] + ',"target_edge_kind":"distinct"}'
    decision = decide_with_contract_fallback(raw, MESSAGE, EVENT, "observed", **TARGET)
    assert decision["error_code"] == "duplicate_key"
    message = "전기포트가 고장입니다. 전원선에서 연기가 났어요 연기가 났어요."
    with pytest.raises(ValidationError, match="quote_nonunique"):
        validate_evidence_graph(
            json.dumps(CURRENT, ensure_ascii=False),
            message,
            {"clause_index": 2, "quote": "연기가 났어요"},
            "observed",
            product_index=1,
            target_mention="전기포트",
        )
