"""Tests for the post-run strict journal parser without new model calls."""

import json
from pathlib import Path

import pytest

from scripts.audit_as_safety_owner_evidence_journal import audit

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
PROTOCOL = DATA / "as-safety-owner-evidence-diagnostic-protocol.v1.json"
JOURNAL = DATA / "as-safety-owner-evidence-diagnostic-result.v1.jsonl"


def test_strict_audit_accepts_frozen_journal() -> None:
    result = audit(PROTOCOL, JOURNAL)
    assert result["summary"]["all"]["denominator"] == 24
    assert result["summary"]["all"]["errors"] == 1


def test_strict_audit_rejects_duplicate_key_hidden_in_begin_row(tmp_path: Path) -> None:
    lines = JOURNAL.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[1]) == {"event": "begin", "case_id": "RE01"}
    lines[1] = '{"event":"begin","case_id":"private utterance","case_id":"RE01"}'
    changed = tmp_path / "tampered.jsonl"
    changed.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON keys"):
        audit(PROTOCOL, changed)
