"""Runner tests with no model, Docker engine, or network access."""

from __future__ import annotations

import json

import pytest

from experiments.as_safety_v2 import run
from experiments.as_safety_v2.cases import load_development_cases
from experiments.as_safety_v2.transport import Completion, RequestPolicy, TransportError


def _case() -> dict:
    return load_development_cases(
        re_dataset=run.INPUTS["re_dataset"],
        v_dataset=run.INPUTS["v_dataset"],
        labels_path=run.INPUTS["labels"],
        spans_path=run.INPUTS["spans"],
        subject_path=run.INPUTS["subject"],
        owner_review_path=run.INPUTS["owner_review"],
    )[0]


def test_stage1_missing_evidence_skips_stage2_and_keeps_raw_private(tmp_path, monkeypatch):
    calls = []

    def complete(messages, schema, *, policy):
        calls.append((messages, schema, policy))
        return Completion(
            content=json.dumps(
                {
                    "event_span": None,
                    "subject_span": None,
                    "owner_span": None,
                    "owner_kind": "unresolved",
                }
            ),
            finish_reason="stop",
        )

    monkeypatch.setattr(run, "post_json_completion", complete)
    result = run.call_case(_case(), RequestPolicy(), tmp_path)
    assert len(calls) == 1
    assert result["stage1"]["status"] == "validated"
    assert result["stage2"]["called"] is False
    assert result["stage2"]["skip_reason"] == "missing_event_subject_owner"
    assert result["source_relation"] == "unknown"
    assert result["route"] == "confirming_safety_status"
    assert '"quote":' not in json.dumps(result)
    assert (tmp_path / "RE01-stage1.json.txt").stat().st_mode & 0o777 == 0o600


def test_transport_failure_records_finite_error_without_stage2(tmp_path, monkeypatch):
    calls = []

    def complete(messages, schema, *, policy):
        calls.append(messages)
        raise TransportError("network_error")

    monkeypatch.setattr(run, "post_json_completion", complete)
    result = run.call_case(_case(), RequestPolicy(), tmp_path)
    assert result["stage1"]["status"] == "response_error"
    assert result["stage1"]["error_code"] == "network_error"
    assert result["stage1"]["raw_sha256"] is None
    assert result["stage2"]["called"] is False
    assert len(calls) == 1
    assert not list(tmp_path.iterdir())


def test_stage1_contract_error_has_field_and_stops_stage2(tmp_path, monkeypatch):
    def complete(messages, schema, *, policy):
        return Completion(content='{"bad":true}', finish_reason="stop")

    monkeypatch.setattr(run, "post_json_completion", complete)
    result = run.call_case(_case(), RequestPolicy(), tmp_path)
    assert result["stage1"]["status"] == "contract_error"
    assert result["stage1"]["error_code"] == "fields_invalid"
    assert result["stage1"]["error_field"] == "stage1"
    assert result["stage2"]["called"] is False


def _stage1_raw(case: dict) -> str:
    return json.dumps(
        {
            field: case[reference]
            for field, reference in (
                ("event_span", "event_reference"),
                ("subject_span", "subject_reference"),
                ("owner_span", "owner_reference"),
            )
        }
        | {"owner_kind": "explicit"},
        ensure_ascii=False,
    )


def test_two_stage_current_response_calls_model_twice(tmp_path, monkeypatch):
    case = _case()
    responses = [
        _stage1_raw(case),
        json.dumps({"source_relation": "current", "distinct_evidence_span": None}),
    ]
    calls = []

    def complete(messages, schema, *, policy):
        calls.append((messages, schema))
        return Completion(responses[len(calls) - 1], "stop")

    monkeypatch.setattr(run, "post_json_completion", complete)
    result = run.call_case(case, RequestPolicy(), tmp_path)
    assert len(calls) == 2
    assert result["stage1"]["status"] == "validated"
    assert result["stage2"]["called"] is True
    assert result["stage2"]["status"] == "validated"
    assert result["stage2"]["model_relation"] == "current"
    assert result["source_relation"] == "current"
    assert result["route"] == "safety_action_required"
    assert (tmp_path / "RE01-stage2.json.txt").exists()
    assert '"quote":' not in json.dumps(result)


@pytest.mark.parametrize(
    ("second_raw", "error_code", "error_field"),
    [
        (
            '{"source_relation":"invalid","distinct_evidence_span":null}',
            "relation_invalid",
            "source_relation",
        ),
        (
            '{"source_relation":"current","distinct_evidence_span":null,"extra":1}',
            "fields_invalid",
            "stage2",
        ),
        (
            '{"source_relation":"other","distinct_evidence_span":{"clause_index":1,"quote":" "}}',
            "quote_blank",
            "distinct_evidence_span",
        ),
    ],
)
def test_stage2_contract_failures_are_bounded(
    tmp_path, monkeypatch, second_raw, error_code, error_field
):
    case = _case()
    calls = []

    def complete(messages, schema, *, policy):
        calls.append(messages)
        content = _stage1_raw(case) if len(calls) == 1 else second_raw
        return Completion(content, "stop")

    monkeypatch.setattr(run, "post_json_completion", complete)
    result = run.call_case(case, RequestPolicy(), tmp_path)
    assert len(calls) == 2
    assert result["stage2"]["called"] is True
    assert result["stage2"]["status"] == "contract_error"
    assert result["stage2"]["error_code"] == error_code
    assert result["stage2"]["error_field"] == error_field
    assert result["stage2"]["model_relation"] is None
    assert result["source_relation"] == "unknown"
    assert result["route"] == "confirming_safety_status"
    assert (tmp_path / "RE01-stage2.json.txt").read_text() == second_raw
    assert '"quote":' not in json.dumps(result)


def test_stage2_transport_failure_does_not_retry_or_write_raw(tmp_path, monkeypatch):
    case = _case()
    calls = []

    def complete(messages, schema, *, policy):
        calls.append(messages)
        if len(calls) == 1:
            return Completion(_stage1_raw(case), "stop")
        raise TransportError("network_error")

    monkeypatch.setattr(run, "post_json_completion", complete)
    result = run.call_case(case, RequestPolicy(), tmp_path)
    assert len(calls) == 2
    assert result["stage2"]["status"] == "response_error"
    assert result["stage2"]["error_code"] == "network_error"
    assert result["stage2"]["raw_sha256"] is None
    assert result["source_relation"] == "unknown"
    assert not (tmp_path / "RE01-stage2.json.txt").exists()
