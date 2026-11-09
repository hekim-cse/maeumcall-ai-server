"""Journal each paired model call without retrying an uncertain exposure."""

from __future__ import annotations

import http.client
import json
import os
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ARMS = ("baseline", "candidate")
ERRORS = (OSError, TimeoutError, ValueError, KeyError, TypeError, http.client.IncompleteRead)


@dataclass(frozen=True)
class Completion:
    """Only response content and bounded termination metadata enter memory."""

    content: str
    finish_reason: str


def _append(file: Any, event: dict) -> None:
    file.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
    file.flush()
    os.fsync(file.fileno())


def run_pair_journal(
    *,
    cases: Iterable[tuple[str, str]],
    journal: Path,
    protocol_sha256: str,
    request: Callable[[str, str], Completion],
    validate: Callable[[str, str], dict],
    route: Callable[[str, dict], str],
) -> None:
    """Create a fresh exposure log; an existing log always needs manual audit.

    A begin event is durable before any model call. An interruption after begin
    can mean the model saw the input, so this function never resumes or replays.
    The request adapter receives a message in memory; the log stores only IDs,
    bounded decisions, routes, stages, and timings.
    """
    if len(protocol_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in protocol_sha256):
        raise ValueError("protocol digest must be SHA-256")
    case_list = list(cases)
    if any(
        not isinstance(case_id, str)
        or not case_id
        or not isinstance(message, str)
        or not message.strip()
        for case_id, message in case_list
    ):
        raise ValueError("invalid case input")
    if len({case_id for case_id, _ in case_list}) != len(case_list):
        raise ValueError("case IDs must be unique")
    if journal.exists():
        raise FileExistsError("existing exposure journal needs manual audit")
    with journal.open("x", encoding="utf-8") as file:
        _append(file, {"event": "header", "protocol_sha256": protocol_sha256})
        for case_index, (case_id, message) in enumerate(case_list):
            order = ARMS if case_index % 2 == 0 else tuple(reversed(ARMS))
            for arm in order:
                _append(file, {"event": "begin", "case_id": case_id, "arm": arm})
                started = time.perf_counter()
                decision = None
                selected_route = None
                error_stage = None
                error_type = None
                finish_reason = None
                try:
                    completion = request(arm, message)
                    if not isinstance(completion, Completion):
                        raise TypeError("request adapter must return Completion")
                    finish_reason = completion.finish_reason
                    if finish_reason != "stop":
                        raise ValueError("model did not finish normally")
                except ERRORS as error:
                    error_stage, error_type = "response", type(error).__name__
                else:
                    try:
                        decision = validate(arm, completion.content)
                    except ERRORS as error:
                        error_stage, error_type = "contract", type(error).__name__
                    else:
                        try:
                            selected_route = route(arm, decision)
                        except ERRORS as error:
                            decision = None
                            error_stage, error_type = "route", type(error).__name__
                _append(
                    file,
                    {
                        "event": "end",
                        "case_id": case_id,
                        "arm": arm,
                        "decision": decision,
                        "route": selected_route,
                        "error_stage": error_stage,
                        "error_type": error_type,
                        "finish_reason": finish_reason
                        if finish_reason in {"stop", "length"}
                        else None,
                        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                    },
                )
