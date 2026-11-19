import json

import pytest

from experiments.as_safety_atomic_edges_v1.run import (
    CALL_ORDER,
    INPUTS,
    SKIP_ORDER,
    _call_event,
    _request_projection,
    load_request_cases,
)
from experiments.as_safety_atomic_edges_v1.verify import (
    VerificationError,
    _review_cell,
    load_edge_labels,
    load_scoring_cases,
    replay_event_owner,
)
from experiments.as_safety_v2.transport import Completion, RequestPolicy


def test_inference_projection_contains_only_allowed_source_fields():
    projected = _request_projection(
        {
            "id": "ES01",
            "user_message": "접수할 선풍기에서 불꽃이 났어요.",
            "target": {"clause_index": 1, "quote": "선풍기"},
            "events": [
                {
                    "event_span": {"clause_index": 1, "quote": "불꽃이 났어요"},
                    "occurrence": "observed",
                    "hazard_owner_span": {"clause_index": 1, "quote": "선풍기"},
                    "owner_to_target": "current",
                    "event_subject_kind": "subject",
                    "event_subject_evidence_span": {
                        "clause_index": 1,
                        "quote": "선풍기에서 불꽃이 났어요",
                    },
                    "target_edge_kind": "part_of",
                    "target_edge_evidence_span": {"clause_index": 1, "quote": "선풍기"},
                    "expected_route": "safety_action_required",
                }
            ],
        }
    )
    assert set(projected) == {
        "case_id",
        "user_message",
        "product_index",
        "target_mention",
        "events",
    }
    assert set(projected["events"][0]) == {"event_index", "event_span", "occurrence"}
    assert "owner_to_target" not in json.dumps(projected, ensure_ascii=False)
    assert "target_edge_kind" not in json.dumps(projected, ensure_ascii=False)


def test_fixed_event_order_has_only_three_nonoccurring_skips():
    assert len(CALL_ORDER) == 19
    assert SKIP_ORDER == ("ES15:2", "ES19:1", "ES20:1")


def test_reviewed_es_inputs_are_projected_without_gold_fields():
    cases = load_request_cases(INPUTS["dataset"])
    assert len(cases) == 20
    assert (
        sum(event["occurrence"] != "nonoccurring" for case in cases for event in case["events"])
        == 19
    )
    assert all(
        set(case)
        == {
            "case_id",
            "user_message",
            "product_index",
            "target_mention",
            "events",
        }
        and all(
            set(event) == {"event_index", "event_span", "occurrence"} for event in case["events"]
        )
        for case in cases
    )


def test_call_event_sends_only_atomic_fields_and_keeps_raw_response_private(tmp_path):
    sent = {}
    output = {
        "subject_span": {"clause_index": 1, "quote": "선풍기"},
        "event_subject_kind": "location",
        "event_subject_evidence_span": {
            "clause_index": 1,
            "quote": "선풍기에서 불꽃이 났어요",
        },
    }

    def fake_completion(messages, schema, *, policy, endpoint, model_id):
        sent.update(
            messages=messages,
            schema=schema,
            policy=policy,
            endpoint=endpoint,
            model_id=model_id,
        )
        return Completion(json.dumps(output, ensure_ascii=False), "stop")

    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    case = {
        "case_id": "ES01",
        "user_message": "접수할 선풍기에서 불꽃이 났어요.",
        "product_index": 1,
        "target_mention": "선풍기",
    }
    event = {
        "event_index": 1,
        "event_span": {"clause_index": 1, "quote": "불꽃이 났어요"},
        "occurrence": "observed",
    }

    row = _call_event(
        case,
        event,
        RequestPolicy(),
        private_dir,
        completion_call=fake_completion,
    )

    assert set(sent["schema"]["properties"]) == {
        "subject_span",
        "event_subject_kind",
        "event_subject_evidence_span",
    }
    assert "B→A" not in "\n".join(message["content"] for message in sent["messages"])
    assert "safety_action_required" not in str(sent["schema"])
    assert row["raw_sha256"] is not None
    assert list(private_dir.iterdir()) == [private_dir / "ES01-event-1.json.txt"]
    assert (private_dir / "ES01-event-1.json.txt").stat().st_mode & 0o777 == 0o600


def test_scoring_projection_omits_expected_routes_and_b_to_a_values():
    cases = load_scoring_cases(INPUTS["dataset"])
    assert len(cases) == 20
    assert (
        sum(event["occurrence"] != "nonoccurring" for case in cases for event in case["events"])
        == 19
    )
    assert all(
        set(case) == {"id", "user_message", "events"}
        and all(
            set(event)
            == {
                "event_span",
                "occurrence",
                "hazard_owner_span",
                "is_current_product_risk",
            }
            for event in case["events"]
        )
        for case in cases
    )


def test_independent_replay_checks_full_direct_evidence_and_unresolved_shape():
    message = "접수할 선풍기에서 불꽃이 났어요."
    valid = {
        "subject_span": {"clause_index": 1, "quote": "선풍기"},
        "event_subject_kind": "location",
        "event_subject_evidence_span": {
            "clause_index": 1,
            "quote": "선풍기에서 불꽃이 났어요",
        },
    }
    replayed = replay_event_owner(
        json.dumps(valid, ensure_ascii=False),
        message,
        {"clause_index": 1, "quote": "불꽃이 났어요"},
    )
    assert replayed["event_subject_kind"] == "location"

    invalid = {
        **valid,
        "event_subject_evidence_span": {"clause_index": 1, "quote": "선풍기"},
    }
    with pytest.raises(VerificationError, match="does not contain"):
        replay_event_owner(
            json.dumps(invalid, ensure_ascii=False),
            message,
            {"clause_index": 1, "quote": "불꽃이 났어요"},
        )

    unresolved = {
        "subject_span": None,
        "event_subject_kind": "unresolved",
        "event_subject_evidence_span": None,
    }
    assert (
        replay_event_owner(
            json.dumps(unresolved),
            "접수할 선풍기에서 불꽃이 났어요.",
            {"clause_index": 1, "quote": "불꽃이 났어요"},
        )["subject_span"]
        is None
    )


def test_review_parser_reads_only_e_to_b_column():
    assert _review_cell("`location` · 2 `충전기에서 불꽃이 났어요`") == (
        "location",
        {"clause_index": 2, "quote": "충전기에서 불꽃이 났어요"},
    )
    assert _review_cell("`unresolved` · `null`") == ("unresolved", None)
    with pytest.raises(VerificationError):
        _review_cell("`part_of` · 2 `부품`")


def test_edge_review_labels_have_only_actionable_es_events():
    labels = load_edge_labels(INPUTS["edge_review"])
    assert len(labels) == 19
    assert labels[("ES17", 1)] == {
        "event_subject_kind": "unresolved",
        "event_subject_evidence_span": None,
    }
