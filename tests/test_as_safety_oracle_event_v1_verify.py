"""Raw-response replay and tamper checks for the conditional oracle journal."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from experiments.as_safety_oracle_event_v1 import run as candidate
from experiments.as_safety_oracle_event_v1 import verify
from experiments.as_safety_v2.transport import Completion, RequestPolicy
from experiments.as_safety_v4.cases import load_cases

MESSAGE = "접수할 전기포트가 고장났습니다. 토스터에서 불꽃이 났습니다. 열은 나지 않았습니다."
CASE = {
    "id": "ES01",
    "user_message": MESSAGE,
    "target": {"clause_index": 1, "quote": "전기포트"},
    "events": [
        {
            "event_span": {"clause_index": 2, "quote": "불꽃이 났습니다"},
            "occurrence": "observed",
            "hazard_owner_span": {"clause_index": 2, "quote": "토스터"},
            "owner_to_target": "other",
        },
        {
            "event_span": {"clause_index": 3, "quote": "열은 나지 않았습니다"},
            "occurrence": "nonoccurring",
            "hazard_owner_span": None,
            "owner_to_target": None,
        },
    ],
    "expected_route": "collecting_service_request",
    "overflow": False,
}


def _candidate(tmp_path: Path, *, raw: str | None = None) -> tuple[dict, Path]:
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    body = raw or json.dumps(
        {"hazard_owner_span": {"clause_index": 2, "quote": "토스터"}, "owner_to_target": "other"},
        ensure_ascii=False,
    )
    calls = []

    def complete(_messages, _schema, *, policy):
        assert isinstance(policy, RequestPolicy)
        calls.append(1)
        return Completion(content=body, finish_reason="stop")

    row = candidate.call_case(CASE, RequestPolicy(), private, completion_call=complete)
    assert len(calls) == 1
    return row, private


def _change(row: dict, path: tuple, value: object) -> dict:
    altered = copy.deepcopy(row)
    item = altered
    for key in path[:-1]:
        item = item[key]
    item[path[-1]] = value
    return altered


def test_runner_raw_replays_with_independent_summary(tmp_path: Path) -> None:
    row, private = _candidate(tmp_path)
    audited = verify.audit_end(row, CASE, private)
    assert audited["route"] == "collecting_service_request"
    assert audited["request_count"] == 1
    assert audited["stage2_called"] == [True, False]
    summary = verify.summarize([audited], [CASE])
    assert summary == {"event": "summary", **candidate.summarize([row], [CASE])}
    assert summary["relation_correct"] == 1
    assert summary["model_involved_route_correct"] == 1


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("route",), "safety_action_required"),
        (("request_count",), 2),
        (("model_call_latency_sum_ms",), 300.0),
        (("stage2", 0, "event_index"), 2),
        (("stage2", 0, "occurrence"), "uncertain"),
        (("stage2", 0, "event_span", "quote_sha256"), "0" * 64),
        (("stage2", 0, "owner_to_target"), "current"),
        (("stage2", 0, "raw_sha256"), "0" * 64),
        (("stage2", 0, "request_latency_ms"), 90000000.0),
        (("stage2", 1, "called"), True),
        (("stage2", 1, "skip_reason"), None),
    ],
)
def test_rejects_public_tampering(tmp_path: Path, path: tuple, value: object) -> None:
    row, private = _candidate(tmp_path)
    with pytest.raises(ValueError):
        verify.audit_end(_change(row, path, value), CASE, private)


def test_rejects_private_raw_tampering(tmp_path: Path) -> None:
    row, private = _candidate(tmp_path)
    path = private / "ES01-stage2-1.json.txt"
    path.write_text('{"owner_to_target":"current"}', encoding="utf-8")
    with pytest.raises(ValueError, match="private raw response differs"):
        verify.audit_end(row, CASE, private)


def test_rejects_forged_contract_error_even_with_matching_raw_hash(tmp_path: Path) -> None:
    raw = '{"hazard_owner_span":null,"owner_to_target":"other"}'
    row, private = _candidate(tmp_path, raw=raw)
    assert row["stage2"][0]["error_code"] == "owner_required"
    verify.audit_end(row, CASE, private)
    forged = _change(row, ("stage2", 0, "error_code"), "relation_invalid")
    with pytest.raises(ValueError, match="contract error differs"):
        verify.audit_end(forged, CASE, private)


def test_owner_span_exact_metric_is_separate_from_relation(tmp_path: Path) -> None:
    raw = json.dumps(
        {
            "hazard_owner_span": {"clause_index": 1, "quote": "전기포트"},
            "owner_to_target": "other",
        },
        ensure_ascii=False,
    )
    row, private = _candidate(tmp_path, raw=raw)
    audited = verify.audit_end(row, CASE, private)
    summary = verify.summarize([audited], [CASE])
    assert summary["relation_correct"] == 1
    assert summary["owner_exact_correct"] == 0
    assert summary["category_relation_correct"]["observed_other"] == 1


def test_rejects_private_permissions(tmp_path: Path) -> None:
    row, private = _candidate(tmp_path)
    path = private / "ES01-stage2-1.json.txt"
    os.chmod(path, 0o644)
    with pytest.raises(ValueError, match="private raw metadata differs"):
        verify.audit_end(row, CASE, private)
    os.chmod(path, 0o600)
    os.chmod(private, 0o755)
    with pytest.raises(ValueError, match="private raw directory boundary"):
        verify._private_dir(private)


def test_rejects_duplicate_json_key_and_missing_raw(tmp_path: Path) -> None:
    raw = '{"owner_to_target":"other","owner_to_target":"current","hazard_owner_span":null}'
    row, private = _candidate(tmp_path, raw=raw)
    assert row["stage2"][0]["error_code"] == "duplicate_key"
    verify.audit_end(row, CASE, private)
    (private / "ES01-stage2-1.json.txt").unlink()
    with pytest.raises(ValueError, match="private raw metadata differs"):
        verify.audit_end(row, CASE, private)


def test_rejects_empty_or_replaced_raw_even_with_rehashed_metadata(tmp_path: Path) -> None:
    row, private = _candidate(tmp_path)
    path = private / "ES01-stage2-1.json.txt"
    path.write_bytes(b" \n")
    row["stage2"][0]["raw_bytes"] = 2
    row["stage2"][0]["raw_sha256"] = hashlib.sha256(b" \n").hexdigest()
    with pytest.raises(ValueError, match="private raw content blank"):
        verify.audit_end(row, CASE, private)


def test_summary_rejects_case_order_and_tampered_public_totals(tmp_path: Path) -> None:
    row, private = _candidate(tmp_path)
    audited = verify.audit_end(row, CASE, private)
    with pytest.raises(ValueError, match="summary case count"):
        verify.summarize([], [CASE])
    with pytest.raises(ValueError, match="summary case order"):
        verify.summarize([{**audited, "case_id": "ES02"}], [CASE])
    assert verify.summarize([audited], [CASE])["request_count"] == 1


def test_full_journal_checks_order_summary_and_raw_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row, private = _candidate(tmp_path)
    audited = verify.audit_end(row, CASE, private)
    summary = verify.summarize([audited], [CASE])
    protocol = tmp_path / "protocol.json"
    protocol.write_text("{}", encoding="utf-8")
    journal = tmp_path / "journal.jsonl"
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")
    monkeypatch.setattr(
        verify, "check_protocol", lambda _p, _m: ({"model_sha256": "a" * 64}, "b" * 64)
    )
    monkeypatch.setattr(verify, "load_cases", lambda _p: [CASE])
    rows = [
        {"event": "header", "protocol_sha256": "b" * 64},
        {"event": "begin", "case_id": "ES01"},
        row,
        summary,
    ]

    def write() -> None:
        journal.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows))

    write()
    result = verify.verify(protocol, journal, private, model_path=model)
    assert result["relation_correct"] == 1
    rows[1] = {"event": "begin", "case_id": "ES02"}
    write()
    with pytest.raises(ValueError, match="journal case order"):
        verify.verify(protocol, journal, private, model_path=model)
    rows[1]["case_id"] = "ES01"
    rows[-1]["relation_correct"] = 0
    write()
    with pytest.raises(ValueError, match="journal summary"):
        verify.verify(protocol, journal, private, model_path=model)
    rows[-1]["relation_correct"] = 1
    write()
    (private / "extra.json.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="private raw file inventory"):
        verify.verify(protocol, journal, private, model_path=model)


def test_all_reviewed_es_cases_replay_conditional_denominators(tmp_path: Path) -> None:
    cases = load_cases(verify.DATASET)
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    rows = []
    audited = []
    for case in cases:
        responses = iter(
            json.dumps(
                {
                    "hazard_owner_span": event["hazard_owner_span"],
                    "owner_to_target": event["owner_to_target"],
                },
                ensure_ascii=False,
            )
            for event in case["events"]
            if event["occurrence"] != "nonoccurring"
        )

        def complete(_messages, _schema, *, policy, _responses=responses):
            assert isinstance(policy, RequestPolicy)
            return Completion(content=next(_responses), finish_reason="stop")

        row = candidate.call_case(case, RequestPolicy(), private, completion_call=complete)
        rows.append(row)
        audited.append(verify.audit_end(row, case, private))
    summary = verify.summarize(audited, cases)
    assert summary == {"event": "summary", **candidate.summarize(rows, cases)}
    assert summary["cases"] == 20
    assert summary["gold_event_count"] == 22
    assert summary["actionable_gold_event_count"] == 19
    assert summary["request_count"] == 19
    assert summary["relation_correct"] == 19
    assert summary["owner_exact_correct"] == 19
    assert summary["category_counts"] == {
        "observed_current": 8,
        "observed_other": 9,
        "observed_unknown": 1,
        "uncertain_current": 1,
    }
    assert summary["category_relation_correct"] == summary["category_counts"]
    assert summary["contrast_pair_count"] == 2
    assert summary["contrast_pairs_correct"] == 2
    assert summary["stage2_errors"] == 0
    assert summary["model_involved_cases"] == 18
    assert summary["model_involved_route_correct"] == 18
    assert summary["multi_event_cases"] == 2
    assert summary["multi_event_route_correct"] == 2
    assert summary["request_latency_p50_ms"] is not None
    assert summary["request_latency_p95_ms"] is not None
