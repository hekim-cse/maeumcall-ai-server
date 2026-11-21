"""Integrity and historical-boundary checks for the offline candidate probe audit."""

from __future__ import annotations

import hashlib
import json

import pytest

from scripts import audit_as_safety_candidate_probe as probe


def test_frozen_probe_reconstruction_matches_public_journal() -> None:
    result = probe.audit()
    assert (
        result["denominator"],
        result["included"],
        result["truncated"],
        result["not_generated"],
        result["exact_selection"],
    ) == (18, 13, 0, 5, 0)
    omissions = {
        (row["case_id"], name): field["omission_reason"]
        for row in result["rows"]
        for name, field in row["fields"].items()
        if field["candidate_status"] == "not_generated"
    }
    assert omissions == {
        ("RE03", "event"): "over_window_limit",
        ("RE06", "event"): "over_window_limit",
        ("RE09", "subject"): "unsupported_final_suffix_or_internal_end",
        ("RE09", "owner"): "unsupported_final_suffix_or_internal_end",
        ("V07", "event"): "over_window_limit",
    }
    assert {row["case_id"]: row["candidate_count"] for row in result["rows"]} == {
        "RE03": 55,
        "RE06": 88,
        "RE09": 58,
        "V01": 42,
        "V04": 52,
        "V07": 39,
    }


def test_protocol_byte_change_is_rejected_before_reconstruction(tmp_path) -> None:
    protocol = tmp_path / "protocol.json"
    protocol.write_bytes(probe.PROTOCOL.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="frozen artifact differs"):
        probe.audit(protocol_path=protocol)


def test_journal_semantic_change_is_rejected_even_with_updated_outer_hash(
    tmp_path, monkeypatch
) -> None:
    rows = [json.loads(line) for line in probe.JOURNAL.read_text(encoding="utf-8").splitlines()]
    target = next(
        row
        for row in rows
        if row.get("case_id") == "RE03" and row.get("method") == "ids" and row.get("event") == "end"
    )
    target["selected_ids"]["subject_id"] = "P010"  # Gold ID; stored output remains P001.
    journal = tmp_path / "journal.jsonl"
    payload = ("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n").encode()
    journal.write_bytes(payload)
    monkeypatch.setattr(probe, "JOURNAL_SHA256", hashlib.sha256(payload).hexdigest())
    with pytest.raises(ValueError, match="selected span differs"):
        probe.audit(journal_path=journal)


def test_later_lattice_sensitivity_reports_availability_without_selection() -> None:
    result = probe.current_lattice_sensitivity()
    assert result["denominator"] == 18
    assert [
        (
            setting["max_window_tokens"],
            setting["included"],
            setting["truncated"],
            setting["not_generated"],
        )
        for setting in result["settings"]
    ] == [(5, 15, 0, 3), (8, 17, 0, 1)]
    assert all("exact_selection" not in setting for setting in result["settings"])
