"""Bounded llama.cpp chat request retaining its termination reason."""

from __future__ import annotations

import json
import urllib.request

from evals.structured_nlu.ai_heldout import AIHeldoutRequestPolicy
from scripts.as_safety_pair_executor_v2 import Completion
from scripts.run_ai_heldout_pair import _loopback_endpoint

MAX_RESPONSE_BYTES = 1_000_000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("model endpoint redirected")


def post_completion(
    endpoint: str,
    model_id: str,
    messages: list[dict[str, str]],
    policy: AIHeldoutRequestPolicy,
    schema: dict,
) -> Completion:
    """Return only content and finish reason; reject oversized or redirected replies."""
    if _loopback_endpoint(endpoint) != "http://127.0.0.1:18081/v1/chat/completions":
        raise ValueError("unexpected local model endpoint")
    payload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": policy.max_tokens,
        "temperature": policy.temperature,
        "repeat_penalty": policy.repeat_penalty,
        "stop": list(policy.stop),
        "response_format": {"type": "json_object", "schema": schema},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    with opener.open(request, timeout=policy.timeout_seconds) as response:
        raw_body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw_body) > MAX_RESPONSE_BYTES:
        raise ValueError("model response too large")
    body = json.loads(raw_body)
    try:
        choice = body["choices"][0]
        content = choice["message"]["content"]
        finish_reason = choice["finish_reason"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("model response fields differ") from error
    if not isinstance(content, str) or not isinstance(finish_reason, str):
        raise ValueError("model response types differ")
    return Completion(content, finish_reason)
