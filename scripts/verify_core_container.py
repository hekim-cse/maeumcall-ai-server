"""Verify the explicit runtime contract of the core AI server container."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

EXPECTED_COMPONENTS = {
    "authentication",
    "ffmpeg",
    "korean_text_analyzer",
    "local_nlu",
    "openai",
    "postgresql",
    "reservation_availability",
    "tts",
    "voice_baseline_security",
}
CORE_UNREADY_COMPONENTS = {"local_nlu"}


class ContainerContractError(RuntimeError):
    """Raised when the running container violates its documented contract."""


@dataclass(frozen=True)
class HttpResult:
    status: int
    body: dict[str, Any]


def _request_json(url: str, *, timeout_seconds: float = 3.0) -> HttpResult:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        status = exc.code

    try:
        body = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContainerContractError(f"{url} did not return valid JSON") from exc

    if not isinstance(body, dict):
        raise ContainerContractError(f"{url} returned a non-object JSON response")
    return HttpResult(status=status, body=body)


def _wait_for_liveness(base_url: str, *, deadline_seconds: float) -> HttpResult:
    deadline = time.monotonic() + deadline_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            result = _request_json(f"{base_url}/health")
            if result.status == 200 and result.body == {"ok": True}:
                return result
            last_error = ContainerContractError(
                f"unexpected liveness response: {result.status} {result.body}"
            )
        except (OSError, ContainerContractError) as exc:
            last_error = exc
        time.sleep(1)

    raise ContainerContractError(
        f"server did not become live within {deadline_seconds:.0f} seconds"
    ) from last_error


def verify_core_runtime(
    base_url: str,
    *,
    deadline_seconds: float,
    expected_version: str,
) -> None:
    normalized_base_url = base_url.rstrip("/")
    _wait_for_liveness(normalized_base_url, deadline_seconds=deadline_seconds)

    metadata = _request_json(f"{normalized_base_url}/")
    if metadata.status != 200:
        raise ContainerContractError(f"metadata status must be 200, got {metadata.status}")
    if metadata.body.get("name") != "MaeumCall AI Server":
        raise ContainerContractError("metadata server name does not match")
    if metadata.body.get("version") != expected_version:
        raise ContainerContractError(
            f"metadata version must be {expected_version}, got {metadata.body.get('version')}"
        )
    if metadata.body.get("docs") != "/docs":
        raise ContainerContractError("metadata docs path does not match")

    readiness = _request_json(f"{normalized_base_url}/health/ready")
    if readiness.status != 503 or readiness.body.get("status") != "not_ready":
        raise ContainerContractError(
            "core runtime must report not_ready until the local NLU runtime is added"
        )

    components = readiness.body.get("components")
    if not isinstance(components, dict) or set(components) != EXPECTED_COMPONENTS:
        raise ContainerContractError("readiness component set does not match the contract")

    local_nlu = components["local_nlu"]
    if not isinstance(local_nlu, dict) or local_nlu.get("ready") is not False:
        raise ContainerContractError("local_nlu must explicitly report ready=false")

    for component_name in EXPECTED_COMPONENTS - CORE_UNREADY_COMPONENTS:
        component = components[component_name]
        if not isinstance(component, dict) or component.get("ready") is not True:
            raise ContainerContractError(f"{component_name} must explicitly report ready=true")

    if components["tts"].get("enabled") is not False:
        raise ContainerContractError("TTS must remain disabled in the core runtime")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the running core AI server container contract."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--deadline-seconds", type=float, default=60.0)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()

    try:
        verify_core_runtime(
            args.base_url,
            deadline_seconds=args.deadline_seconds,
            expected_version=args.expected_version,
        )
    except ContainerContractError as exc:
        parser.exit(1, f"container contract verification failed: {exc}\n")

    print("core container contract verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
