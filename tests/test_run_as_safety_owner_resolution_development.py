"""Check two-stage call boundaries without contacting the model."""

import json
from types import SimpleNamespace
from unittest.mock import patch

from scripts.run_as_safety_owner_resolution_development import _call

CASE = {
    "id": "RE09",
    "user_message": "접수할 건 거실 TV의 화면 깜빡임입니다. 옆에 둔 오래된 멀티탭에서는 어제 연기가 났습니다.",
    "expected_relation": {"product_index": 1, "event_status": "observed"},
}
SPAN = {"target_mention": "TV"}


def _response(content):
    return SimpleNamespace(content=json.dumps(content, ensure_ascii=False), finish_reason="stop")


def _stage1(owner=True):
    return {
        "event_span": {"clause_index": 2, "quote": "연기"},
        "subject_span": {"clause_index": 2, "quote": "오래된 멀티탭"},
        "owner_span": {"clause_index": 2, "quote": "오래된 멀티탭"} if owner else None,
        "owner_kind": "explicit" if owner else "unresolved",
        "cue_spans": [{"clause_index": 2, "quote": "옆에 둔"}] if owner else [],
        "distinct_cue_index": 0 if owner else None,
    }


def test_two_stage_success_is_quote_free_and_counts_two_calls():
    responses = [_response(_stage1()), _response({"source_relation": "other"})]
    with patch(
        "scripts.run_as_safety_owner_resolution_development.post_completion", side_effect=responses
    ) as mock:
        row = _call(CASE, SPAN, {}, None)
    assert mock.call_count == 2
    assert row["source_relation"] == "other"
    assert row["route"] == "collecting_service_request"
    assert row["stage1"]["status"] == row["stage2"]["status"] == "validated"
    assert '"quote":' not in json.dumps(row, ensure_ascii=False)
    assert row["stage1"]["spans"]["owner_span"]["quote_sha256"]


def test_missing_owner_skips_second_call_and_keeps_denominator():
    with patch(
        "scripts.run_as_safety_owner_resolution_development.post_completion",
        return_value=_response(_stage1(owner=False)),
    ) as mock:
        row = _call(CASE, SPAN, {}, None)
    assert mock.call_count == 1
    assert row["source_relation"] == "unknown"
    assert row["stage2"]["skip_reason"] == "missing_event_subject_owner"
    assert row["route"] == "confirming_safety_status"


def test_stage_one_contract_error_skips_second_call():
    with patch(
        "scripts.run_as_safety_owner_resolution_development.post_completion",
        return_value=_response({"bad": 1}),
    ) as mock:
        row = _call(CASE, SPAN, {}, None)
    assert mock.call_count == 1
    assert row["stage1"]["status"] == "contract_error"
    assert row["stage2"]["skip_reason"] == "stage1_invalid"
    assert row["source_relation"] == "unknown"


def test_stage_one_transport_error_does_not_retry_or_call_stage_two():
    with patch(
        "scripts.run_as_safety_owner_resolution_development.post_completion",
        side_effect=OSError("offline"),
    ) as mock:
        row = _call(CASE, SPAN, {}, None)
    assert mock.call_count == 1
    assert row["stage1"]["status"] == "response_error"
    assert row["stage2"]["status"] == "skipped"
    assert row["stage2"]["skip_reason"] == "stage1_invalid"
    assert row["source_relation"] == "unknown"
    assert row["route"] == "confirming_safety_status"


def test_stage_two_transport_error_does_not_retry():
    with patch(
        "scripts.run_as_safety_owner_resolution_development.post_completion",
        side_effect=[_response(_stage1()), OSError("offline")],
    ) as mock:
        row = _call(CASE, SPAN, {}, None)
    assert mock.call_count == 2
    assert row["stage1"]["status"] == "validated"
    assert row["stage2"]["status"] == "response_error"
    assert row["stage2"]["error"] == "response_error"
    assert row["source_relation"] == "unknown"
    assert row["route"] == "confirming_safety_status"
