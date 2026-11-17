"""Offline audit must handle valid transport-error journals without false matches."""

import json

from experiments.as_safety_dual_query_v1 import offline_audit
from experiments.as_safety_dual_query_v1.run import REQUEST


def test_missing_raw_is_not_an_identical_response_and_none_decisions_sort(monkeypatch, tmp_path):
    protocol_path = tmp_path / "protocol.json"
    journal_path = tmp_path / "journal.jsonl"
    protocol_path.write_text(
        json.dumps({"event_order": ["ES01-1", "ES02-1"], "request_policy": REQUEST}),
        encoding="utf-8",
    )
    rows = [
        {"event": "end", "event_id": "ES01-1", "arm": arm, "stage": stage}
        for arm, stage in (
            ("current", {"raw_sha256": None, "decision": None}),
            ("distinct", {"raw_sha256": None, "decision": None}),
        )
    ] + [
        {"event": "end", "event_id": "ES02-1", "arm": arm, "stage": stage}
        for arm, stage in (
            ("current", {"raw_sha256": "same", "decision": "yes"}),
            ("distinct", {"raw_sha256": "same", "decision": "yes"}),
        )
    ]
    journal_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    monkeypatch.setattr(
        offline_audit,
        "verify",
        lambda *_args, **_kwargs: {
            "protocol_sha256": "protocol",
            "journal_sha256": "journal",
            "private_raw_count": 2,
        },
    )
    result = offline_audit.audit(protocol_path, journal_path, tmp_path, tmp_path)
    assert result["same_raw_response_pairs"] == 1
    assert result["pairs_with_missing_raw_response"] == 1
    assert result["gold_category_and_decisions"] == [
        {
            "category": "observed_current",
            "current_question": None,
            "distinct_question": None,
            "count": 1,
        },
        {
            "category": "observed_current",
            "current_question": "yes",
            "distinct_question": "yes",
            "count": 1,
        },
    ]
