"""Check bounded response decoding without a live model server."""

import http.client
import json
from pathlib import Path

import pytest

from evals.structured_nlu.ai_heldout import AIHeldoutRequestPolicy
from scripts import as_safety_completion_v2


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, limit):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body[:limit]


class FakeOpener:
    def __init__(self, body):
        self.body = body

    def open(self, request, timeout):
        assert request.full_url == "http://127.0.0.1:18081/v1/chat/completions"
        assert timeout > 0
        return FakeResponse(self.body)


def policy():
    return AIHeldoutRequestPolicy.model_validate_json(
        Path("evals/structured_nlu/data/ai_heldout/q4-q5-request-policy.v1.json").read_bytes()
    )


def call(monkeypatch, body):
    monkeypatch.setattr(
        as_safety_completion_v2.urllib.request, "build_opener", lambda *args: FakeOpener(body)
    )
    return as_safety_completion_v2.post_completion(
        "http://127.0.0.1:18081/v1/chat/completions",
        "/models/test.gguf",
        [{"role": "user", "content": "private"}],
        policy(),
        {"type": "object"},
    )


def test_finish_reason_is_retained(monkeypatch):
    body = json.dumps(
        {"choices": [{"message": {"content": "{}"}, "finish_reason": "length"}]}
    ).encode()
    completion = call(monkeypatch, body)
    assert completion.content == "{}"
    assert completion.finish_reason == "length"


def test_truncated_body_propagates_for_executor_to_record(monkeypatch):
    with pytest.raises(http.client.IncompleteRead):
        call(monkeypatch, http.client.IncompleteRead(b"partial", 3))


def test_missing_finish_reason_is_response_error(monkeypatch):
    with pytest.raises(ValueError, match="fields differ"):
        call(monkeypatch, b'{"choices":[{"message":{"content":"{}"}}]}')


def test_oversized_response_is_rejected(monkeypatch):
    with pytest.raises(ValueError, match="too large"):
        call(monkeypatch, b"x" * (as_safety_completion_v2.MAX_RESPONSE_BYTES + 1))
