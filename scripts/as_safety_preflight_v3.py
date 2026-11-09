"""Verify frozen source digests before any next-version model exposure."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from pathlib import Path

from scripts.as_safety_pair_executor_v3 import Completion, run_pair_journal

EXECUTOR_SOURCE = Path(__file__).with_name("as_safety_pair_executor_v3.py")
VERIFIER_SOURCE = Path(__file__).with_name("verify_as_safety_pair_journal_v3.py")
SHAPE_VERIFIER_SOURCE = Path(__file__).with_name("verify_as_safety_pair_journal_v2.py")
ERROR_AUDIT_SOURCE = Path(__file__).with_name("audit_as_safety_pair_errors.py")


def verify_frozen_sources(
    protocol_path: Path, additional_sources: dict[str, Path] | None = None
) -> None:
    """Reject missing, malformed, or changed digests before creating a journal."""
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    source_paths = {
        "executor_sha256": EXECUTOR_SOURCE,
        "verifier_sha256": VERIFIER_SOURCE,
        "preflight_sha256": Path(__file__),
        "journal_shape_sha256": SHAPE_VERIFIER_SOURCE,
        "error_audit_sha256": ERROR_AUDIT_SOURCE,
    }
    if additional_sources:
        if source_paths.keys() & additional_sources.keys():
            raise ValueError("mandatory source path cannot be overridden")
        source_paths.update(additional_sources)
    for key, path in source_paths.items():
        expected = protocol.get(key)
        if (
            not isinstance(expected, str)
            or len(expected) != 64
            or any(character not in "0123456789abcdef" for character in expected)
        ):
            raise ValueError(f"missing or invalid {key}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"frozen {key} differs")


def run_frozen_pair(
    *,
    protocol_path: Path,
    additional_sources: dict[str, Path] | None = None,
    cases: Iterable[tuple[str, str]],
    journal: Path,
    request: Callable[[str, str], Completion],
    validate: Callable[[str, str, str], dict],
    route: Callable[[str, dict], str],
) -> None:
    """Bind frozen-source validation to execution before the first model call."""
    verify_frozen_sources(protocol_path, additional_sources)
    run_pair_journal(
        cases=cases,
        journal=journal,
        protocol_sha256=hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        request=request,
        validate=validate,
        route=route,
    )
