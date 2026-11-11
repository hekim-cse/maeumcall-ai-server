"""Guard the neutral entity-link model request and no-raw-text journal boundary."""

from __future__ import annotations

import json
import urllib.error
from types import SimpleNamespace

import pytest

from scripts import run_as_safety_entity_link_diagnostic as runner


def _first_case():
    return runner.load_gold_owner_cases(
        runner.SOURCE_PATHS["spans_sha256"], runner.SOURCE_PATHS["owner_labels_sha256"]
    )[0]


def test_request_uses_only_reviewed_target_and_owner_anchors(monkeypatch):
    case, span, owner = _first_case()
    calls = []

    def fake_post(_endpoint, _model, messages, _policy, schema):
        calls.append((messages, schema))
        return SimpleNamespace(content='{"entity_link":"same_or_part"}', finish_reason="stop")

    monkeypatch.setattr(runner, "post_completion", fake_post)
    row = runner._call(case, span, owner, object())
    assert len(calls) == 1
    messages, schema = calls[0]
    prompt = json.dumps(messages, ensure_ascii=False)
    assert case["user_message"] in prompt
    assert span["target_mention"] in prompt
    assert owner["mention"] in prompt
    assert "검수된 위험 사건 구절" not in prompt
    assert "고정된 위험 발생 상태" not in prompt
    assert "accepted_link_kinds" not in prompt
    assert "expected_relation" not in prompt
    assert "source_relation" not in prompt
    assert set(schema["properties"]) == {"entity_link"}
    assert row["entity_link"] == "same_or_part"
    assert row["source_relation"] == "current"
    assert case["user_message"] not in json.dumps(row, ensure_ascii=False)
    assert owner["mention"] not in json.dumps(row, ensure_ascii=False)


@pytest.mark.parametrize(
    ("content", "link", "relation", "route"),
    [
        ("same_or_part", "same_or_part", "current", "safety_action_required"),
        ("distinct_item", "distinct_item", "other", "collecting_service_request"),
        ("unresolved", "unresolved", "unknown", "confirming_safety_status"),
    ],
)
def test_single_entity_decision_maps_only_after_model_call(
    monkeypatch, content, link, relation, route
):
    case, span, owner = _first_case()
    monkeypatch.setattr(
        runner,
        "post_completion",
        lambda *_args: SimpleNamespace(
            content=json.dumps({"entity_link": content}), finish_reason="stop"
        ),
    )
    row = runner._call(case, span, owner, object())
    assert (row["entity_link"], row["source_relation"], row["route"]) == (
        link,
        relation,
        route,
    )


@pytest.mark.parametrize(
    ("response", "stage", "code", "finish", "status"),
    [
        (
            SimpleNamespace(content="{", finish_reason="stop"),
            "contract",
            "invalid_json",
            "stop",
            None,
        ),
        (
            SimpleNamespace(content='{"entity_link":"bad"}', finish_reason="stop"),
            "contract",
            "invalid_relation",
            "stop",
            None,
        ),
        (
            SimpleNamespace(content='{"entity_link":"same_or_part"}', finish_reason="length"),
            "response",
            "finish_length",
            "length",
            None,
        ),
        (
            urllib.error.HTTPError("http://127.0.0.1/", 503, "private body", None, None),
            "response",
            "http_error",
            None,
            503,
        ),
    ],
)
def test_failed_call_retains_no_decision_or_response(
    monkeypatch, response, stage, code, finish, status
):
    case, span, owner = _first_case()
    calls = 0

    def fake_post(*_args):
        nonlocal calls
        calls += 1
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(runner, "post_completion", fake_post)
    row = runner._call(case, span, owner, object())
    assert calls == 1
    assert (row["error_stage"], row["error_code"], row["finish_reason"], row["http_status"]) == (
        stage,
        code,
        finish,
        status,
    )
    assert row["entity_link"] is row["source_relation"] is row["route"] is None
    assert "private body" not in json.dumps(row)
