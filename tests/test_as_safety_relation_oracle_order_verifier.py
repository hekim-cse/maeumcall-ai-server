"""Independent audit checks for the relation-only prompt-order experiment."""

import hashlib
import json
import os

import pytest

from experiments.as_safety_relation_oracle_order_v1 import verify as auditor


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ('{"relation":"different"}', "relation_enum_invalid"),
        ('{"relation":null}', "relation_enum_invalid"),
        ('{"relation":"current","extra":0}', "relation_fields_invalid"),
        ('{"relation":"current","relation":"other"}', "duplicate_key"),
        ('{"relation":"current","x":NaN}', "nonfinite_number"),
        ('["current"]', "relation_fields_invalid"),
        ('{"relation":', "invalid_json"),
    ],
)
def test_replay_rejects_noncontract_raw(raw, code):
    with pytest.raises(auditor.ContractError) as caught:
        auditor.replay_relation(raw)
    assert caught.value.code == code


@pytest.mark.parametrize("relation", ["current", "other", "unknown"])
def test_replay_accepts_only_one_valid_field(relation):
    assert auditor.replay_relation('{"relation":"' + relation + '"}') == relation


def test_raw_tamper_and_permissions_are_detected(tmp_path):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    path = directory / "ES01-1-forward.json.txt"
    raw = b'{"relation":"current"}'
    path.write_bytes(raw)
    os.chmod(path, 0o600)
    stage = {"raw_sha256": hashlib.sha256(raw).hexdigest(), "raw_bytes": len(raw)}
    auditor._private_dir(directory)
    assert auditor._read_raw(stage, path) == raw.decode()
    path.write_bytes(b'{"relation":"other"}')
    with pytest.raises(ValueError, match="raw response differs"):
        auditor._read_raw(stage, path)
    path.write_bytes(raw)
    os.chmod(path, 0o644)
    with pytest.raises(ValueError, match="raw metadata differs"):
        auditor._read_raw(stage, path)
    os.chmod(path, 0o600)
    os.chmod(directory, 0o755)
    with pytest.raises(ValueError, match="directory boundary differs"):
        auditor._private_dir(directory)


def test_route_replay_preserves_safety_precedence():
    events = [{"occurrence": "observed"}, {"occurrence": "observed"}]
    assert auditor._route(events, ["current", None], failed=True) == "safety_action_required"
    assert auditor._route(events, ["other", None], failed=True) == "confirming_safety_status"
    assert auditor._route(events, ["other", "other"], failed=False) == "collecting_service_request"
    assert auditor._route([{"occurrence": "uncertain"}], ["current"], failed=False) == "confirming_safety_status"


@pytest.fixture
def complete_journal(tmp_path, monkeypatch):
    """Build a 36-call fixture; mock only the Git/model freeze prerequisite."""
    cases = auditor.load_cases(auditor.DATASET)
    selected = auditor._eligible_events(cases)
    assignments = [
        {"event_id": key, "arms": list(auditor.ARMS if i % 2 == 0 else reversed(auditor.ARMS))}
        for i, (key, _, _, _) in enumerate(selected)
    ]
    protocol = {"event_order": [item["event_id"] for item in assignments], "arm_order": assignments}
    monkeypatch.setattr(auditor, "check_protocol", lambda *_args: (protocol, "a" * 64))
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    rows = [{"event": "header", "protocol_sha256": "a" * 64}]
    audited = {}
    gold_by_id = {key: gold for key, _, _, gold in selected}
    for assignment in assignments:
        event_id = assignment["event_id"]
        for arm in assignment["arms"]:
            relation = gold_by_id[event_id]["owner_to_target"]
            raw = json.dumps({"relation": relation}).encode()
            name = f"{event_id}-{arm}.json.txt"
            path = private / name
            path.write_bytes(raw)
            os.chmod(path, 0o600)
            stage = {
                "called": True, "status": "validated", "skip_reason": None,
                "error_code": None, "error_field": None, "finish_reason": "stop",
                "latency_ms": 3.0, "request_latency_ms": 2.0,
                "raw_sha256": hashlib.sha256(raw).hexdigest(), "raw_bytes": len(raw),
                "relation": relation,
            }
            rows.extend((
                {"event": "begin", "event_id": event_id, "arm": arm},
                {"event": "end", "event_id": event_id, "arm": arm, "stage": stage},
            ))
            audited[(event_id, arm)] = {"status": "validated", "relation": relation, "request_latency_ms": 2.0}
    rows.append(auditor.summarize(audited, cases))
    journal = tmp_path / "journal.jsonl"

    def write():
        journal.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    write()
    return rows, write, journal, private


def test_complete_journal_replays_and_reaches_gate(complete_journal):
    _, _, journal, private = complete_journal
    result = auditor.verify(auditor.DATASET, journal, private, model_path=journal)
    assert result["private_raw_count"] == 36
    assert result["summary"]["gate_met"] is True
    assert result["summary"]["arms"]["forward"]["route_correct"] == 17


def test_independent_summary_agrees_with_runner_on_frozen_shape(complete_journal):
    from experiments.as_safety_relation_oracle_order_v1 import run as runner

    rows, _, _, _ = complete_journal
    cases = auditor.load_cases(auditor.DATASET)
    runner_summary = runner.summarize([row for row in rows if row["event"] == "end"], cases)
    assert rows[-1] == {"event": "summary", **runner_summary}


@pytest.mark.parametrize("tamper", ["swap", "retry", "route", "summary", "extra_field"])
def test_journal_order_retry_and_aggregate_tamper_rejected(complete_journal, tamper):
    rows, write, journal, private = complete_journal
    if tamper == "swap":
        rows[1], rows[3] = rows[3], rows[1]
    elif tamper == "retry":
        rows[3:3] = rows[1:3]
    elif tamper == "route":
        rows[-1]["arms"]["forward"]["route_predictions"]["ES01"] = "collecting_service_request"
    elif tamper == "summary":
        rows[-1]["paired"]["both_correct"] = 0
    else:
        rows[2]["stage"]["unexpected"] = True
    write()
    with pytest.raises(ValueError):
        auditor.verify(auditor.DATASET, journal, private, model_path=journal)


@pytest.mark.parametrize(
    ("raw", "code", "field"),
    [
        (b'{"relation":"current","relation":"other"}', "duplicate_key", "$"),
        (b'{"relation":"different"}', "relation_enum_invalid", "relation"),
    ],
)
def test_contract_error_raw_replayed_in_full_journal(complete_journal, raw, code, field):
    rows, write, journal, private = complete_journal
    row = rows[2]
    path = private / "ES01-1-forward.json.txt"
    path.write_bytes(raw)
    stage = row["stage"]
    stage.update(
        status="contract_error", error_code=code, error_field=field,
        raw_sha256=hashlib.sha256(raw).hexdigest(), raw_bytes=len(raw), relation=None,
    )
    # Rebuild the published aggregate after the raw contract error.
    cases = auditor.load_cases(auditor.DATASET)
    audited = {
        (item["event_id"], item["arm"]): {
            "status": item["stage"]["status"],
            "relation": item["stage"]["relation"],
            "request_latency_ms": item["stage"]["request_latency_ms"],
        }
        for item in rows if item["event"] == "end"
    }
    rows[-1] = auditor.summarize(audited, cases)
    write()
    result = auditor.verify(auditor.DATASET, journal, private, model_path=journal)
    assert result["summary"]["arms"]["forward"]["contract_errors"] == 1
    assert result["summary"]["arms"]["forward"]["route_predictions"]["ES01"] == "confirming_safety_status"
    assert result["summary"]["gate_met"] is False
    stage["error_code"] = "incorrect_code"
    write()
    with pytest.raises(ValueError, match="contract result differs"):
        auditor.verify(auditor.DATASET, journal, private, model_path=journal)
