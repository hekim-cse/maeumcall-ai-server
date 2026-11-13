"""Verify one bounded local request without contacting a model server."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from experiments.as_safety_v2.transport import (
    ENDPOINT,
    MAX_RESPONSE_BYTES,
    MODEL_ID,
    RequestPolicy,
    TransportError,
    _NoRedirect,
    post_json_completion,
)

MESSAGES = [{"role": "user", "content": "TV에서 연기가 났어요."}]
SCHEMA = {"type": "object"}


class FakeResponse:
    status = 200

    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


class FakeOpener:
    def __init__(self, response: FakeResponse | Exception) -> None:
        self.response = response
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _reply(content: str = '{"owner_span":null}', finish: object = "stop") -> bytes:
    return json.dumps(
        {"choices": [{"message": {"content": content}, "finish_reason": finish}]}
    ).encode()


def test_one_deterministic_local_request_without_proxy_or_redirect(monkeypatch):
    opener = FakeOpener(FakeResponse(_reply()))
    handlers = []

    def build_opener(*args):
        handlers.extend(args)
        return opener

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)
    result = post_json_completion(MESSAGES, SCHEMA)
    assert (result.content, result.finish_reason) == ('{"owner_span":null}', "stop")
    assert len(opener.calls) == 1
    request, timeout = opener.calls[0]
    assert (request.full_url, request.get_method(), timeout) == (ENDPOINT, "POST", 180)
    payload = json.loads(request.data)
    assert payload == {
        "model": MODEL_ID,
        "messages": MESSAGES,
        "max_tokens": 320,
        "temperature": 0,
        "repeat_penalty": 1.05,
        "stop": ["<|eot_id|>"],
        "seed": 0,
        "response_format": {"type": "json_object", "schema": SCHEMA},
    }
    assert any(
        type(handler) is urllib.request.ProxyHandler and handler.proxies == {}
        for handler in handlers
    )
    assert any(type(handler) is _NoRedirect for handler in handlers)


@pytest.mark.parametrize(
    "endpoint",
    ["http://localhost:18081/v1/chat/completions", "http://127.0.0.1:8000/v1/chat/completions"],
)
def test_only_declared_loopback_endpoint_is_allowed(endpoint):
    with pytest.raises(ValueError, match="endpoint"):
        post_json_completion(MESSAGES, SCHEMA, endpoint=endpoint)


def test_oversized_request_is_rejected_before_network(monkeypatch):
    monkeypatch.setattr(urllib.request, "build_opener", lambda *_: pytest.fail("network opened"))
    with pytest.raises(TransportError) as caught:
        post_json_completion([{"role": "user", "content": "가" * 100_000}], SCHEMA)
    assert caught.value.code == "request_too_large"


@pytest.mark.parametrize(
    ("response", "expected_code"),
    [
        (FakeResponse(b"{"), "invalid_response_json"),
        (FakeResponse(_reply(content="")), "response_fields_invalid"),
        (FakeResponse(_reply(finish="tool_calls")), "response_fields_invalid"),
        (FakeResponse(_reply(finish=[])), "response_fields_invalid"),
        (FakeResponse(_reply(finish={})), "response_fields_invalid"),
        (FakeResponse(_reply(), status=201), "http_status"),
        (FakeResponse(b"x" * (MAX_RESPONSE_BYTES + 1)), "response_too_large"),
        (TimeoutError("secret body"), "timeout"),
        (urllib.error.HTTPError(ENDPOINT, 503, "secret body", None, None), "http_error"),
    ],
)
def test_response_failures_are_bounded_and_never_retried(monkeypatch, response, expected_code):
    opener = FakeOpener(response)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *_: opener)
    with pytest.raises(TransportError) as caught:
        post_json_completion(MESSAGES, SCHEMA)
    assert caught.value.code == expected_code
    assert "secret body" not in str(caught.value)
    assert len(opener.calls) == 1


def test_redirect_is_rejected_without_request_replay():
    with pytest.raises(TransportError) as caught:
        _NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://example.com")
    assert caught.value.code == "redirect"


@pytest.mark.parametrize(
    "kwargs",
    [{"temperature": 1}, {"max_tokens": 0}, {"timeout_seconds": 0}, {"seed": -1}],
)
def test_request_policy_rejects_nondeterministic_or_unbounded_settings(kwargs):
    with pytest.raises(ValueError):
        RequestPolicy(**kwargs)
