"""Bounded, local-only llama.cpp transport for A/S development experiments."""

from __future__ import annotations

import http.client
import json
import math
import urllib.error
import urllib.request
from dataclasses import dataclass

from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json

ENDPOINT = "http://127.0.0.1:18081/v1/chat/completions"
MODEL_ID = "/models/kanana.gguf"
MAX_REQUEST_BYTES = 256_000
MAX_RESPONSE_BYTES = 1_000_000


class TransportError(Exception):
    """Finite transport failure without the request or model output in text."""

    def __init__(self, code: str, status_code: int | None = None) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(code)


@dataclass(frozen=True)
class RequestPolicy:
    max_tokens: int = 320
    temperature: int = 0
    repeat_penalty: float = 1.05
    stop: tuple[str, ...] = ("<|eot_id|>",)
    timeout_seconds: int = 180
    seed: int = 0

    def __post_init__(self) -> None:
        if type(self.max_tokens) is not int or not 1 <= self.max_tokens <= 4096:
            raise ValueError("max_tokens must be 1..4096")
        if type(self.temperature) is not int or self.temperature != 0:
            raise ValueError("temperature must be zero")
        if (
            type(self.repeat_penalty) not in {int, float}
            or not math.isfinite(self.repeat_penalty)
            or not 0 < self.repeat_penalty <= 2
        ):
            raise ValueError("repeat_penalty must be finite and in (0,2]")
        if (
            type(self.stop) is not tuple
            or not 1 <= len(self.stop) <= 4
            or any(type(item) is not str or not item or len(item) > 64 for item in self.stop)
        ):
            raise ValueError("stop must be a bounded tuple of strings")
        if type(self.timeout_seconds) is not int or not 1 <= self.timeout_seconds <= 300:
            raise ValueError("timeout_seconds must be 1..300")
        if type(self.seed) is not int or not 0 <= self.seed <= 2**32 - 1:
            raise ValueError("seed must be an unsigned 32-bit integer")


@dataclass(frozen=True)
class Completion:
    content: str
    finish_reason: str


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise TransportError("redirect")


def post_json_completion(
    messages: list[dict[str, str]],
    schema: dict,
    *,
    policy: RequestPolicy | None = None,
    endpoint: str = ENDPOINT,
    model_id: str = MODEL_ID,
) -> Completion:
    """Issue exactly one local request; return bounded content and finish reason."""
    if endpoint != ENDPOINT or model_id != MODEL_ID:
        raise ValueError("unexpected local model endpoint or model ID")
    if (
        type(messages) is not list
        or not messages
        or any(
            type(message) is not dict
            or set(message) != {"role", "content"}
            or type(message["role"]) is not str
            or message["role"] not in {"system", "user", "assistant"}
            or type(message["content"]) is not str
            for message in messages
        )
        or type(schema) is not dict
    ):
        raise ValueError("request messages or schema differ")
    request_policy = policy if policy is not None else RequestPolicy()
    if type(request_policy) is not RequestPolicy:
        raise ValueError("request policy differs")
    payload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": request_policy.max_tokens,
        "temperature": request_policy.temperature,
        "repeat_penalty": request_policy.repeat_penalty,
        "stop": list(request_policy.stop),
        "seed": request_policy.seed,
        "response_format": {"type": "json_object", "schema": schema},
    }
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_REQUEST_BYTES:
        raise TransportError("request_too_large")
    request = urllib.request.Request(
        endpoint,
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=request_policy.timeout_seconds) as response:
            if response.status != 200:
                raise TransportError("http_status", response.status)
            raw_body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        raise TransportError("http_error", error.code) from None
    except urllib.error.URLError:
        raise TransportError("network_error") from None
    except TimeoutError:
        raise TransportError("timeout") from None
    except http.client.HTTPException:
        raise TransportError("network_error") from None
    except OSError:
        raise TransportError("network_error") from None
    if type(raw_body) is not bytes or len(raw_body) > MAX_RESPONSE_BYTES:
        raise TransportError("response_too_large")
    try:
        body = parse_model_json(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, ValidationError):
        raise TransportError("invalid_response_json") from None
    if type(body) is not dict or type(body.get("choices")) is not list or not body["choices"]:
        raise TransportError("response_fields_invalid")
    choice = body["choices"][0]
    if type(choice) is not dict or type(choice.get("message")) is not dict:
        raise TransportError("response_fields_invalid")
    content = choice["message"].get("content")
    finish = choice.get("finish_reason")
    if (
        type(content) is not str
        or not content.strip()
        or type(finish) is not str
        or finish not in {"stop", "length"}
    ):
        raise TransportError("response_fields_invalid")
    return Completion(content=content, finish_reason=finish)
