"""Apply stricter postrun error invariants without changing frozen model-call code."""

from __future__ import annotations


def audit_error_semantics(events: list[dict]) -> None:
    for event in events:
        if event.get("event") != "end" or event["error_stage"] is None:
            continue
        stage = event["error_stage"]
        if event["decision"] is not None:
            raise ValueError("failed call retains decision")
        if stage in {"contract", "route"} and event["finish_reason"] != "stop":
            raise ValueError("postresponse error finish reason differs")
        if stage == "response" and event["finish_reason"] not in {None, "length"}:
            raise ValueError("response error finish reason differs")
