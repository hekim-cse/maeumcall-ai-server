"""Audit next-version paired journals and all error-stage metadata."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_as_safety_pair_errors import audit_error_semantics
from scripts.verify_as_safety_pair_journal_v2 import verify_journal as verify_shape_and_order


class _JournalSnapshot:
    """Present one immutable read to the frozen v2 structural verifier."""

    def __init__(self, text: str):
        self.text = text

    def read_text(self, **_kwargs) -> str:
        return self.text


def verify_journal(path: Path, case_ids: list[str], protocol_sha256: str) -> dict:
    """Recompute order and error counts, then reject impossible error records."""
    journal_text = path.read_text(encoding="utf-8")
    summary = verify_shape_and_order(_JournalSnapshot(journal_text), case_ids, protocol_sha256)
    events = [json.loads(line) for line in journal_text.splitlines()]
    audit_error_semantics(events)
    for event in events:
        if event.get("event") == "end" and event["error_stage"] is not None:
            if not event["error_type"].strip():
                raise ValueError("error type is blank")
    return summary
