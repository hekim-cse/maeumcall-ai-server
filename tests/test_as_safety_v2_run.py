"""Runner tests with no model, Docker engine, or network access."""

from __future__ import annotations

import json

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
    assert "quote" not in json.dumps(result)
    assert (tmp_path / "RE01-stage1.json.txt").stat().st_mode & 0o777 == 0o600


def test_transport_failure_records_finite_error_without_stage2(tmp_path, monkeypatch):
    def complete(messages, schema, *, policy):
        raise TransportError("network_error")

    monkeypatch.setattr(run, "post_json_completion", complete)
    result = run.call_case(_case(), RequestPolicy(), tmp_path)
    assert result["stage1"]["status"] == "response_error"
    assert result["stage1"]["error_code"] == "network_error"
    assert result["stage1"]["raw_sha256"] is None
    assert result["stage2"]["called"] is False
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
