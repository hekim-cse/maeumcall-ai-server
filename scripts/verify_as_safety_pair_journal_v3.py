"""Audit next-version paired journals and all error-stage metadata."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_as_safety_pair_errors import audit_error_semantics
from scripts.verify_as_safety_pair_journal_v2 import verify_journal as verify_shape_and_order


def verify_journal(path: Path, case_ids: list[str], protocol_sha256: str) -> dict:
    """Recompute order and error counts, then reject impossible error records."""
    summary = verify_shape_and_order(path, case_ids, protocol_sha256)
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    audit_error_semantics(events)
    return summary
