"""Independent raw replay and corruption checks for both Stage2 ablation arms."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from experiments.as_safety_stage2_ablation_v1 import run as candidate
from experiments.as_safety_stage2_ablation_v1 import verify
from experiments.as_safety_v2.transport import Completion, RequestPolicy, TransportError
from experiments.as_safety_v4.cases import load_cases

CASE = {
    "id": "ES01",
    "user_message": (
        "접수할 전기포트가 고장났습니다. 토스터에서 불꽃이 났습니다. 열은 나지 않았습니다."
    ),
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


def _raw(arm: str, *, relation: str = "other") -> str:
    if arm == "R":
        return json.dumps({"owner_to_target": relation})
    return json.dumps(
        {
            "hazard_owner_span": {"clause_index": 2, "quote": "토스터"},
            "owner_to_target": relation,
        },
        ensure_ascii=False,
    )


def _candidate(tmp_path: Path, arm: str, *, raw: str | None = None) -> tuple[dict, Path]:
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    calls = []

    def complete(_messages, _schema, *, policy):
        assert isinstance(policy, RequestPolicy)
        calls.append(1)
        return Completion(content=raw if raw is not None else _raw(arm), finish_reason="stop")

    row = candidate.call_case(arm, CASE, RequestPolicy(), private, completion_call=complete)
    assert len(calls) == 1
    return row, private


@pytest.mark.parametrize("arm", ["R", "O"])
def test_replays_both_arms_and_matches_runner_metrics(tmp_path: Path, arm: str) -> None:
    row, private = _candidate(tmp_path, arm)
    audited = verify.audit_end(row, CASE, arm, private)
    assert audited["route"] == "collecting_service_request"
    assert audited["request_count"] == 1
    assert audited["stage2_called"] == [True, False]
    summary = verify.summarize_arm([audited], [CASE], arm)
    assert summary == candidate.summarize_arm(arm, [row], [CASE])
    assert summary["relation_correct"] == 1
    assert summary["model_involved_route_correct"] == 1
    assert summary["skip_nonoccurring"] == 1


@pytest.mark.parametrize("arm", ["R", "O"])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("route", "safety_action_required"),
        ("request_count", 2),
        ("model_call_latency_sum_ms", 999999.0),
    ],
)
def test_rejects_public_row_tampering(tmp_path: Path, arm: str, field: str, value: object) -> None:
    row, private = _candidate(tmp_path, arm)
    corrupted = copy.deepcopy(row)
    corrupted[field] = value
    with pytest.raises(ValueError):
        verify.audit_end(corrupted, CASE, arm, private)


@pytest.mark.parametrize("arm", ["R", "O"])
def test_rejects_stage_and_private_raw_tampering(tmp_path: Path, arm: str) -> None:
    row, private = _candidate(tmp_path, arm)
    corrupted = copy.deepcopy(row)
    corrupted["stage2"][0]["owner_to_target"] = "current"
    with pytest.raises(ValueError, match="public decision differs"):
        verify.audit_end(corrupted, CASE, arm, private)
    path = private / f"{arm}-ES01-stage2-1.json.txt"
    path.write_text(_raw(arm, relation="current"), encoding="utf-8")
    with pytest.raises(ValueError, match="private raw response differs"):
        verify.audit_end(row, CASE, arm, private)


@pytest.mark.parametrize("arm", ["R", "O"])
def test_rejects_private_permission_and_rehashed_blank(tmp_path: Path, arm: str) -> None:
    row, private = _candidate(tmp_path, arm)
    path = private / f"{arm}-ES01-stage2-1.json.txt"
    os.chmod(path, 0o644)
    with pytest.raises(ValueError, match="private raw metadata differs"):
        verify.audit_end(row, CASE, arm, private)
    os.chmod(path, 0o600)
    path.write_bytes(b" \n")
    row["stage2"][0]["raw_bytes"] = 2
    row["stage2"][0]["raw_sha256"] = hashlib.sha256(b" \n").hexdigest()
    with pytest.raises(ValueError, match="private raw content blank"):
        verify.audit_end(row, CASE, arm, private)


@pytest.mark.parametrize("arm", ["R", "O"])
def test_network_error_replays_without_raw(tmp_path: Path, arm: str) -> None:
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    calls = 0

    def fail(_messages, _schema, *, policy):
        nonlocal calls
        assert isinstance(policy, RequestPolicy)
        calls += 1
        raise TransportError("network_error")

    row = candidate.call_case(arm, CASE, RequestPolicy(), private, completion_call=fail)
    assert calls == 1
    assert row["stage2"][0]["raw_sha256"] is None
    assert list(private.iterdir()) == []
    audited = verify.audit_end(row, CASE, arm, private)
    assert audited["route"] == "confirming_safety_status"
    assert verify.summarize_arm([audited], [CASE], arm)["stage2_errors"] == 1


@pytest.mark.parametrize("arm", ["R", "O"])
def test_length_finish_replays_with_raw(tmp_path: Path, arm: str) -> None:
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    calls = 0

    def truncated(_messages, _schema, *, policy):
        nonlocal calls
        assert isinstance(policy, RequestPolicy)
        calls += 1
        return Completion(content=_raw(arm), finish_reason="length")

    row = candidate.call_case(arm, CASE, RequestPolicy(), private, completion_call=truncated)
    assert calls == 1
    assert row["stage2"][0]["raw_sha256"] is not None
    assert [path.name for path in private.iterdir()] == [f"{arm}-ES01-stage2-1.json.txt"]
    audited = verify.audit_end(row, CASE, arm, private)
    assert audited["route"] == "confirming_safety_status"
    assert verify.summarize_arm([audited], [CASE], arm)["stage2_errors"] == 1


@pytest.mark.parametrize(
    ("arm", "raw", "expected_code"),
    [
        ("R", '{"owner_to_target":"same"}', "relation_invalid"),
        (
            "O",
            '{"hazard_owner_span":{"clause_index":2,"quote":"토스터"},"owner_to_target":"same"}',
            "relation_invalid",
        ),
        (
            "O",
            '{"hazard_owner_span":null,"owner_to_target":"unknown","extra":true}',
            "fields_invalid",
        ),
    ],
)
def test_invalid_relation_and_extra_field_replay_to_confirmation(
    tmp_path: Path, arm: str, raw: str, expected_code: str
) -> None:
    row, private = _candidate(tmp_path, arm, raw=raw)
    assert row["request_count"] == 1
    assert row["stage2"][0]["status"] == "contract_error"
    assert row["stage2"][0]["error_code"] == expected_code
    assert row["stage2"][0]["raw_sha256"] is not None
    audited = verify.audit_end(row, CASE, arm, private)
    assert audited["route"] == "confirming_safety_status"
    summary = verify.summarize_arm([audited], [CASE], arm)
    assert summary["request_count"] == 1
    assert summary["stage2_errors"] == 1


def test_relation_only_contract_rejects_extra_field_and_duplicate_key() -> None:
    with pytest.raises(Exception, match="fields_invalid"):
        verify._relation_only('{"owner_to_target":"other","extra":true}')
    with pytest.raises(Exception, match="duplicate_key"):
        verify._relation_only('{"owner_to_target":"other","owner_to_target":"current"}')


def test_o_skips_missing_owner_and_fails_to_confirmation(tmp_path: Path) -> None:
    case = copy.deepcopy(CASE)
    case["events"][0]["hazard_owner_span"] = None
    case["events"][0]["owner_to_target"] = "unknown"
    case["expected_route"] = "confirming_safety_status"
    private = tmp_path / "private"
    private.mkdir(mode=0o700)

    def unexpected(_messages, _schema, *, policy):
        raise AssertionError("owner-null case must not call model")

    row = candidate.call_case("O", case, RequestPolicy(), private, completion_call=unexpected)
    assert row["request_count"] == 0
    assert row["stage2"][0]["skip_reason"] == "owner_oracle_unavailable"
    audited = verify.audit_end(row, case, "O", private)
    assert audited["route"] == "confirming_safety_status"
    summary = verify.summarize_arm([audited], [case], "O")
    assert summary["skip_owner_unavailable"] == 1
    assert summary["eligible_gold_event_count"] == 0


def test_all_es_cases_have_frozen_arm_denominators(tmp_path: Path) -> None:
    cases = load_cases(verify.DATASET)
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    for arm, expected in (("R", 19), ("O", 18)):
        rows = []
        audited = []
        for case in cases:
            responses = iter(
                _raw(arm, relation=event["owner_to_target"])
                if arm == "R"
                else json.dumps(
                    {
                        "hazard_owner_span": event["hazard_owner_span"],
                        "owner_to_target": event["owner_to_target"],
                    },
                    ensure_ascii=False,
                )
                for event in case["events"]
                if event["occurrence"] != "nonoccurring"
                and (arm == "R" or event["hazard_owner_span"] is not None)
            )

            def complete(_messages, _schema, *, policy, _responses=responses):
                assert isinstance(policy, RequestPolicy)
                return Completion(content=next(_responses), finish_reason="stop")

            row = candidate.call_case(arm, case, RequestPolicy(), private, completion_call=complete)
            rows.append(row)
            audited.append(verify.audit_end(row, case, arm, private))
        summary = verify.summarize_arm(audited, cases, arm)
        assert summary == candidate.summarize_arm(arm, rows, cases)
        assert summary["eligible_gold_event_count"] == expected
        assert summary["request_count"] == expected
        assert summary["relation_correct"] == expected
        assert summary["category_relation_correct"] == summary["category_counts"]
        assert summary["model_involved_cases"] == (18 if arm == "R" else 17)
        assert summary["model_involved_route_correct"] == (18 if arm == "R" else 17)
        assert summary["contrast_pairs_correct"] == 2
        assert summary["skip_nonoccurring"] == 3
        assert summary["skip_owner_unavailable"] == (0 if arm == "R" else 1)


def test_full_journal_order_summary_and_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    rows_by_arm = {}
    for arm in verify.ARMS:

        def complete(_messages, _schema, *, policy, _arm=arm):
            return Completion(content=_raw(_arm), finish_reason="stop")

        rows_by_arm[arm] = candidate.call_case(
            arm, CASE, RequestPolicy(), private, completion_call=complete
        )
    baseline = {
        "relation_correct_all": 7,
        "relation_correct_owner_available": 7,
        "model_involved_route_correct_all": 6,
        "model_involved_route_correct_owner_available": 6,
        "owner_available_event_count": 18,
        "owner_available_model_involved_cases": 17,
    }
    monkeypatch.setattr(
        verify, "check_protocol", lambda _p, _m: ({"model_sha256": "a" * 64}, "b" * 64)
    )
    monkeypatch.setattr(verify, "baseline_paired", lambda _p, _m: baseline)
    monkeypatch.setattr(verify, "load_cases", lambda _p: [CASE])
    document = [{"event": "header", "protocol_sha256": "b" * 64}]
    for arm in verify.ARMS:
        document.extend(
            [
                {"event": "begin", "arm": arm, "case_id": CASE["id"]},
                rows_by_arm[arm],
            ]
        )
    document.append(
        {
            "event": "summary",
            "arms": {
                arm: verify.summarize_arm(
                    [verify.audit_end(rows_by_arm[arm], CASE, arm, private)], [CASE], arm
                )
                for arm in verify.ARMS
            },
            "baseline_paired": baseline,
        }
    )
    journal = tmp_path / "journal.jsonl"

    def write() -> None:
        journal.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in document)
        )

    write()
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")
    assert (
        verify.verify(journal, journal, private, private, model_path=model)["arms"]["R"][
            "relation_correct"
        ]
        == 1
    )
    initial_bytes = journal.read_bytes()
    original_read_bytes = Path.read_bytes
    original_read_text = Path.read_text
    journal_reads = {"bytes": 0, "text": 0}

    def racing_read_bytes(path: Path) -> bytes:
        content = original_read_bytes(path)
        if path == journal:
            journal_reads["bytes"] += 1
            journal.write_bytes(b"changed after the snapshot")
        return content

    def racing_read_text(path: Path, *args, **kwargs) -> str:
        content = original_read_text(path, *args, **kwargs)
        if path == journal:
            journal_reads["text"] += 1
            journal.write_bytes(b"changed after the text read")
        return content

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", racing_read_bytes)
        patch.setattr(Path, "read_text", racing_read_text)
        result = verify.verify(journal, journal, private, private, model_path=model)
    assert journal_reads == {"bytes": 1, "text": 0}
    assert result["journal_sha256"] == hashlib.sha256(initial_bytes).hexdigest()
    write()
    document[1]["arm"] = "O"
    write()
    with pytest.raises(ValueError, match="journal arm or case order"):
        verify.verify(journal, journal, private, private, model_path=model)
    document[1]["arm"] = "R"
    document[-1]["arms"]["O"]["relation_correct"] = 0
    write()
    with pytest.raises(ValueError, match="journal summary differs"):
        verify.verify(journal, journal, private, private, model_path=model)
    document[-1]["arms"]["O"]["relation_correct"] = 1
    write()
    (private / "extra.json.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="private raw file inventory"):
        verify.verify(journal, journal, private, private, model_path=model)


def test_protocol_rejects_changed_frozen_source_input_and_uncommitted_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "verify.py"
    source.write_bytes(b"frozen source")
    data = tmp_path / "data.json"
    data.write_bytes(b"frozen input")
    protocol_path = tmp_path / "protocol.json"
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")
    frozen = {"verify.py": source.read_bytes(), "data.json": data.read_bytes()}
    monkeypatch.setattr(verify, "ROOT", tmp_path)
    monkeypatch.setattr(verify, "INPUTS", {"dataset": data})
    monkeypatch.setattr(verify, "_sources", lambda _commit: {"verify.py"})
    monkeypatch.setattr(verify.prior, "_frozen", lambda _commit, path: frozen[path])
    monkeypatch.setattr(verify.prior, "_digest_file", lambda _path: verify.MODEL_SHA)
    protocol = {
        "kind": verify.KIND,
        "claim_scope": verify.SCOPE,
        "case_order": list(verify.CASE_ORDER),
        "frozen_code_commit": "a" * 40,
        "input_hashes": {"dataset": hashlib.sha256(data.read_bytes()).hexdigest()},
        "source_manifest": {"verify.py": hashlib.sha256(source.read_bytes()).hexdigest()},
        "model_sha256": verify.MODEL_SHA,
        "server_image_digest": verify.IMAGE,
        "request_policy": verify.POLICY,
        "local_runtime": verify.RUNTIME,
        "retry_policy": "no_retry_manual_audit_on_interruption",
        "private_output": "outside_repository_mode_0700_files_0600",
    }
    raw = (json.dumps(protocol) + "\n").encode()
    protocol_path.write_bytes(raw)
    monkeypatch.setattr(verify.prior, "_git", lambda *args: raw)
    assert verify.check_protocol(protocol_path, model)[1] == hashlib.sha256(raw).hexdigest()
    source.write_bytes(b"changed source")
    with pytest.raises(ValueError, match="source manifest differs"):
        verify.check_protocol(protocol_path, model)
    source.write_bytes(frozen["verify.py"])
    data.write_bytes(b"changed input")
    with pytest.raises(ValueError, match="input manifest differs"):
        verify.check_protocol(protocol_path, model)
    data.write_bytes(frozen["data.json"])
    monkeypatch.setattr(verify.prior, "_git", lambda *args: b"different committed bytes")
    with pytest.raises(ValueError, match="protocol must be committed"):
        verify.check_protocol(protocol_path, model)
