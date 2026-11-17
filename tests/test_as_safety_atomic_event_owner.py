"""Boundary tests for the development-only E→B atomic contract."""

import json

import pytest

from experiments.as_safety_atomic_edges_v1.event_owner import (
    event_owner_messages,
    event_owner_schema,
    validate_event_owner,
)
from experiments.as_safety_evidence_graph_v1 import verify as graph_verify
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v4.cases import load_cases

MESSAGE = (
    "접수할 휴대용 프린터가 멈췄습니다. 다른 기기의 충전기에서 불꽃이 튀었어요. "
    "프린터 옆면이 뜨거워져 플라스틱이 녹았습니다."
)
TARGET = {"product_index": 1, "target_mention": "휴대용 프린터"}
FIRST_EVENT = {"clause_index": 2, "quote": "불꽃이 튀었어요"}
SECOND_EVENT = {"clause_index": 3, "quote": "프린터 옆면이 뜨거워져"}
FIRST_OUTPUT = {
    "subject_span": {"clause_index": 2, "quote": "다른 기기의 충전기"},
    "event_subject_kind": "location",
    "event_subject_evidence_span": {
        "clause_index": 2,
        "quote": "다른 기기의 충전기에서 불꽃이 튀었어요",
    },
}


def _validate(payload, *, event=FIRST_EVENT, message=MESSAGE, occurrence="observed"):
    return validate_event_owner(
        json.dumps(payload, ensure_ascii=False),
        message,
        event,
        occurrence,
        **TARGET,
    )


def test_prompt_and_schema_exclude_gold_owner_relation_and_route():
    prompt = "\n".join(
        item["content"] for item in event_owner_messages(MESSAGE, FIRST_EVENT, "observed", **TARGET)
    )
    assert "검수된 위험 사건 E: 2. 불꽃이 튀었어요" in prompt
    assert "다른 기기의 충전기" in prompt  # The original user utterance is visible.
    assert "current" not in prompt and "other" not in prompt
    assert "safety_action_required" not in prompt
    schema = event_owner_schema(MESSAGE)
    assert set(schema["required"]) == set(FIRST_OUTPUT)
    assert schema["additionalProperties"] is False


def test_two_events_in_one_utterance_are_validated_independently():
    first = _validate(FIRST_OUTPUT)
    assert first["subject_span"]["quote"] == "다른 기기의 충전기"
    second = _validate(
        {
            "subject_span": {"clause_index": 3, "quote": "프린터 옆면"},
            "event_subject_kind": "subject",
            "event_subject_evidence_span": {
                "clause_index": 3,
                "quote": "프린터 옆면이 뜨거워져",
            },
        },
        event=SECOND_EVENT,
    )
    assert second["subject_span"]["clause_index"] == 3
    assert "effective_relation" not in first and "effective_relation" not in second


def test_unknown_owner_requires_all_spans_null():
    message = "접수할 휴대용 프린터가 멈췄습니다. 불꽃이 튀었는데 어느 기기인지 모르겠어요."
    event = {"clause_index": 2, "quote": "불꽃이 튀었는데"}
    unresolved = {
        "subject_span": None,
        "event_subject_kind": "unresolved",
        "event_subject_evidence_span": None,
    }
    assert _validate(unresolved, message=message, event=event)["subject_span"] is None
    with pytest.raises(ValidationError, match="attachment_consistency_invalid"):
        _validate(
            {**unresolved, "subject_span": {"clause_index": 1, "quote": "프린터"}},
            message=message,
            event=event,
        )


def test_direct_quote_must_link_both_event_and_subject():
    wrong_event = {
        **FIRST_OUTPUT,
        "event_subject_evidence_span": {"clause_index": 2, "quote": "다른 기기의 충전기"},
    }
    with pytest.raises(ValidationError, match="direct_attachment_unlinked"):
        _validate(wrong_event)
    wrong_subject = {**FIRST_OUTPUT, "subject_span": {"clause_index": 3, "quote": "프린터 옆면"}}
    with pytest.raises(ValidationError, match="direct_attachment_unlinked"):
        _validate(wrong_subject)

    partial_event = {
        **FIRST_OUTPUT,
        "event_subject_evidence_span": {
            "clause_index": 2,
            "quote": "다른 기기의 충전기에서 불꽃이",
        },
    }
    with pytest.raises(ValidationError, match="direct_attachment_unlinked"):
        _validate(partial_event)


def test_uncertain_event_prompt_does_not_assert_occurrence():
    prompt = "\n".join(
        item["content"]
        for item in event_owner_messages(MESSAGE, FIRST_EVENT, "uncertain", **TARGET)
    )
    assert "발생 상태: uncertain" in prompt
    assert "실제로 발생한" not in prompt


def test_implicit_evidence_may_be_in_prior_clause_but_is_not_semantically_verified():
    message = "접수할 휴대용 프린터가 멈췄습니다. 그 제품에서 연기가 났어요."
    event = {"clause_index": 2, "quote": "연기가 났어요"}
    output = {
        "subject_span": {"clause_index": 1, "quote": "휴대용 프린터"},
        "event_subject_kind": "implicit",
        "event_subject_evidence_span": {"clause_index": 1, "quote": "휴대용 프린터"},
    }
    assert _validate(output, message=message, event=event)["event_subject_kind"] == "implicit"


def test_wrong_clause_index_and_duplicate_quote_are_rejected():
    wrong_index = {
        **FIRST_OUTPUT,
        "subject_span": {"clause_index": 3, "quote": "다른 기기의 충전기"},
    }
    with pytest.raises(ValidationError, match="quote_unanchored"):
        _validate(wrong_index)
    message = "접수할 휴대용 프린터가 멈췄습니다. 충전기에서 충전기에서 불꽃이 튀었어요."
    duplicated = {
        "subject_span": {"clause_index": 2, "quote": "충전기"},
        "event_subject_kind": "location",
        "event_subject_evidence_span": {"clause_index": 2, "quote": "충전기에서 불꽃이 튀었어요"},
    }
    with pytest.raises(ValidationError, match="quote_nonunique"):
        _validate(duplicated, message=message)


def test_nonoccurring_event_is_not_a_model_call():
    with pytest.raises(ValidationError, match="occurrence_not_callable"):
        event_owner_messages(MESSAGE, FIRST_EVENT, "nonoccurring", **TARGET)
    with pytest.raises(ValidationError, match="occurrence_not_callable"):
        _validate(FIRST_OUTPUT, occurrence="nonoccurring")


def test_approved_es_edge_labels_fit_the_atomic_quote_contract():
    """Check old labels against the new format; this is not a model score."""
    cases = load_cases(graph_verify.DATASET)
    labels = graph_verify.load_labels(graph_verify.LABELS, cases)
    count = 0
    for case, label_case in zip(cases, labels, strict=True):
        for event, label in zip(case["events"], label_case["events"], strict=True):
            if event["occurrence"] == "nonoccurring":
                continue
            gold_triple = {
                "subject_span": event["hazard_owner_span"],
                "event_subject_kind": label["event_subject_kind"],
                "event_subject_evidence_span": label["event_subject_evidence_span"],
            }
            validate_event_owner(
                json.dumps(gold_triple, ensure_ascii=False),
                case["user_message"],
                event["event_span"],
                event["occurrence"],
                product_index=case["target"]["clause_index"],
                target_mention=case["target"]["quote"],
            )
            count += 1
    assert count == 19
