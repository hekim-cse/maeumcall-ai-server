"""Tamper checks for the development baseline's independent verifier."""

from __future__ import annotations

import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from evals.structured_nlu.ai_heldout import load_reviewed_ai_heldout
from evals.structured_nlu.metrics import score_predictions
from evals.structured_nlu.schema import CasePrediction, EvaluationAttempt
from experiments.nlu_current_baseline_v1 import run as baseline_runner
from experiments.nlu_current_baseline_v1 import verify as auditor


def _boundary(phase: str, completed: int, restart_generation: int) -> dict:
    return {
        "event": "server_boundary",
        "phase": phase,
        "completed_cases": completed,
        "running": True,
        "oom_killed": False,
        "exit_code": 0,
        "restart_count": 0,
        "memory_usage": "1GiB / 10GiB",
        "healthy": True,
        "started_at": f"2026-11-16T00:00:0{restart_generation}Z",
        "container_id": "a" * 64,
        "docker_host_memory_bytes": auditor.RUNTIME["docker_host_min_memory_bytes"],
    }


@pytest.fixture
def complete_result(tmp_path, monkeypatch):
    reviewed = load_reviewed_ai_heldout(auditor.DATASET, auditor.LEDGER)
    raw = b"{}"
    raw_sha = hashlib.sha256(raw).hexdigest()
    predictions = tuple(
        CasePrediction(
            case_id=case.id,
            attempts=(
                EvaluationAttempt(
                    contract_valid=False,
                    latency_ms=1.0,
                    output=None,
                    error_type="StructuredKeyError",
                ),
                EvaluationAttempt(
                    contract_valid=False,
                    latency_ms=1.0,
                    output=None,
                    error_type="StructuredKeyError",
                ),
            ),
        )
        for case in reviewed.dataset.cases
    )
    result = {
        "kind": auditor.RESULT_KIND,
        "protocol_sha256": "a" * 64,
        "predictions": [item.model_dump(mode="json") for item in predictions],
        "summary": score_predictions(reviewed.dataset.cases, predictions).to_dict(),
    }
    private_dir = tmp_path / "raw"
    private_dir.mkdir(mode=0o700)
    rows = [
        {"event": "header", "protocol_sha256": "a" * 64},
        _boundary("initial", 0, 0),
    ]
    for case_number, prediction in enumerate(result["predictions"], start=1):
        rows.append({"event": "begin", "case_id": prediction["case_id"]})
        for ordinal in (1, 2):
            path = private_dir / f"{prediction['case_id']}-attempt{ordinal}.txt"
            path.write_bytes(raw)
            path.chmod(0o600)
        rows.append(
            {
                "event": "end",
                "case_id": prediction["case_id"],
                "prediction": prediction,
                "raw_attempts": [
                    {
                        "attempt": ordinal,
                        "status": "received",
                        "raw_sha256": raw_sha,
                        "raw_bytes": len(raw),
                        "error_type": None,
                    }
                    for ordinal in (1, 2)
                ],
            }
        )
        if case_number in (8, 16, 24):
            rows.append(_boundary("before_restart", case_number, case_number // 8 - 1))
            rows.append(_boundary("after_restart", case_number, case_number // 8))
    rows.append(_boundary("final", 32, 3))
    rows.append({"event": "summary", "summary": result["summary"]})
    journal = tmp_path / "journal.jsonl"
    journal.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    result["journal_sha256"] = hashlib.sha256(journal.read_bytes()).hexdigest()
    monkeypatch.setattr(
        auditor,
        "check_protocol",
        lambda _protocol, _model: ({"request_policy": auditor.REQUEST}, "a" * 64),
    )
    path = tmp_path / "result.json"

    def write(value):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    return result, write, journal, private_dir


def test_complete_artifact_replays_all_32_cases(complete_result, tmp_path):
    result, write, journal, private_dir = complete_result
    replay = auditor.verify(
        tmp_path / "protocol.json",
        write(result),
        journal,
        private_dir,
        tmp_path / "model.gguf",
    )
    assert replay["case_count"] == 32
    assert replay["summary"]["counts"]["fully_correct_cases"] == 0
    assert replay["claim_scope"] == auditor.SCOPE


def _valid_unknown_raw(case) -> str:
    return json.dumps(
        {
            "intent": "service_request",
            "user_action": "unknown",
            "change_field": None,
            "fields": {name: None for name in case.labels.fields},
        },
        ensure_ascii=False,
    )


def test_valid_contract_raw_replays_to_one_exact_case(complete_result, tmp_path):
    result, write, journal, private_dir = complete_result
    reviewed = load_reviewed_ai_heldout(auditor.DATASET, auditor.LEDGER)
    case = reviewed.dataset.cases[1]
    assert case.id == "ai-heldout-ah02"
    assert case.labels.user_action == "unknown"
    raw = _valid_unknown_raw(case).encode("utf-8")
    prediction = auditor._run_case(
        case,
        endpoint=auditor.REQUEST["endpoint"],
        model_id=auditor.REQUEST["model_id"],
        policy=SimpleNamespace(**auditor.REQUEST),
        completion_post=lambda *_args: raw.decode("utf-8"),
    )
    assert len(prediction.attempts) == 1
    assert prediction.attempts[0].contract_valid is True
    assert prediction.attempts[0].output.model_dump(mode="json") == {
        "intent": "service_request",
        "user_action": "unknown",
        "change_field": None,
        "fields": {name: None for name in case.labels.fields},
    }

    result["predictions"][1] = prediction.model_dump(mode="json")
    all_predictions = tuple(CasePrediction.model_validate(item) for item in result["predictions"])
    result["summary"] = score_predictions(reviewed.dataset.cases, all_predictions).to_dict()
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    end = next(row for row in rows if row.get("event") == "end" and row.get("case_id") == case.id)
    end["prediction"] = result["predictions"][1]
    end["raw_attempts"] = [
        {
            "attempt": 1,
            "status": "received",
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "raw_bytes": len(raw),
            "error_type": None,
        }
    ]
    first = private_dir / f"{case.id}-attempt1.txt"
    first.write_bytes(raw)
    first.chmod(0o600)
    (private_dir / f"{case.id}-attempt2.txt").unlink()
    rows[-1]["summary"] = result["summary"]
    journal.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    result["journal_sha256"] = hashlib.sha256(journal.read_bytes()).hexdigest()

    replay = auditor.verify(
        tmp_path / "protocol.json",
        write(result),
        journal,
        private_dir,
        tmp_path / "model.gguf",
    )
    assert replay["summary"]["counts"]["fully_correct_cases"] == 1
    assert replay["summary"]["counts"]["final_contract_passes"] == 1


@pytest.mark.parametrize(
    ("first_raw", "second_raw", "expected_errors", "final_valid"),
    [
        (
            {"user_action": "invalid_action"},
            None,
            ("ValueError", None),
            True,
        ),
        (
            {"user_action": "invalid_action"},
            {"fields_extra": "unexpected"},
            ("ValueError", "StructuredKeyError"),
            False,
        ),
    ],
)
def test_live_analyzer_retry_contract_outcomes(first_raw, second_raw, expected_errors, final_valid):
    reviewed = load_reviewed_ai_heldout(auditor.DATASET, auditor.LEDGER)
    case = reviewed.dataset.cases[1]
    valid = json.loads(_valid_unknown_raw(case))

    def payload(change):
        value = copy.deepcopy(valid)
        if change is None:
            return json.dumps(value, ensure_ascii=False)
        if "fields_extra" in change:
            value["fields"][change["fields_extra"]] = "x"
        else:
            value.update(change)
        return json.dumps(value, ensure_ascii=False)

    responses = iter((payload(first_raw), payload(second_raw)))
    prediction = auditor._run_case(
        case,
        endpoint=auditor.REQUEST["endpoint"],
        model_id=auditor.REQUEST["model_id"],
        policy=SimpleNamespace(**auditor.REQUEST),
        completion_post=lambda *_args: next(responses),
    )
    assert len(prediction.attempts) == 2
    assert tuple(attempt.error_type for attempt in prediction.attempts) == expected_errors
    assert prediction.attempts[0].contract_valid is False
    assert prediction.attempts[-1].contract_valid is final_valid
    assert (prediction.final_output is not None) is final_valid


def test_live_analyzer_normalizes_blank_field_to_null():
    reviewed = load_reviewed_ai_heldout(auditor.DATASET, auditor.LEDGER)
    case = reviewed.dataset.cases[0]
    fields = {
        name: None if expected is None else expected.accepted_values[0]
        for name, expected in case.labels.fields.items()
    }
    fields["symptom"] = " "
    raw = json.dumps(
        {
            "intent": case.labels.intent,
            "user_action": case.labels.user_action,
            "change_field": case.labels.change_field,
            "fields": fields,
        },
        ensure_ascii=False,
    )
    prediction = auditor._run_case(
        case,
        endpoint=auditor.REQUEST["endpoint"],
        model_id=auditor.REQUEST["model_id"],
        policy=SimpleNamespace(**auditor.REQUEST),
        completion_post=lambda *_args: raw,
    )
    assert len(prediction.attempts) == 1
    assert prediction.attempts[0].contract_valid is True
    assert prediction.final_output.fields["symptom"] is None
    assert prediction.final_output.fields["product_type"] == fields["product_type"]


def test_completed_result_with_one_missing_completion_is_rejected(complete_result, tmp_path):
    result, write, journal, private_dir = complete_result
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    first = result["predictions"][0]
    first["attempts"][0]["error_type"] = "ValueError"
    rows[3]["prediction"] = first
    rows[3]["raw_attempts"][0] = {
        "attempt": 1,
        "status": "transport_error",
        "raw_sha256": None,
        "raw_bytes": None,
        "error_type": "ValueError",
    }
    (private_dir / f"{first['case_id']}-attempt1.txt").unlink()
    reviewed = load_reviewed_ai_heldout(auditor.DATASET, auditor.LEDGER)
    predictions = tuple(CasePrediction.model_validate(item) for item in result["predictions"])
    result["summary"] = score_predictions(reviewed.dataset.cases, predictions).to_dict()
    rows[-1]["summary"] = result["summary"]
    journal.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    result["journal_sha256"] = hashlib.sha256(journal.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="completion reception errors make result non-publishable"):
        auditor.verify(
            tmp_path / "protocol.json",
            write(result),
            journal,
            private_dir,
            tmp_path / "model.gguf",
        )


def test_private_raw_replays_and_modified_bytes_are_rejected(complete_result, tmp_path):
    result, write, journal, private_dir = complete_result
    reviewed = load_reviewed_ai_heldout(auditor.DATASET, auditor.LEDGER)
    case = reviewed.dataset.cases[0]
    raw = b"{}"
    prediction = auditor._run_case(
        case,
        endpoint=auditor.REQUEST["endpoint"],
        model_id=auditor.REQUEST["model_id"],
        policy=SimpleNamespace(**auditor.REQUEST),
        completion_post=lambda *_args: raw.decode(),
    )
    assert len(prediction.attempts) == 2
    result["predictions"][0] = prediction.model_dump(mode="json")
    all_predictions = tuple(CasePrediction.model_validate(item) for item in result["predictions"])
    result["summary"] = score_predictions(reviewed.dataset.cases, all_predictions).to_dict()
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    rows[3]["prediction"] = result["predictions"][0]
    rows[3]["raw_attempts"] = []
    for ordinal in (1, 2):
        path = private_dir / f"{case.id}-attempt{ordinal}.txt"
        path.write_bytes(raw)
        path.chmod(0o600)
        rows[3]["raw_attempts"].append(
            {
                "attempt": ordinal,
                "status": "received",
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "raw_bytes": len(raw),
                "error_type": None,
            }
        )
    rows[-1]["summary"] = result["summary"]
    journal.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    result["journal_sha256"] = hashlib.sha256(journal.read_bytes()).hexdigest()
    auditor.verify(
        tmp_path / "protocol.json",
        write(result),
        journal,
        private_dir,
        tmp_path / "model.gguf",
    )
    (private_dir / f"{case.id}-attempt1.txt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="private raw response differs"):
        auditor.verify(
            tmp_path / "protocol.json",
            write(result),
            journal,
            private_dir,
            tmp_path / "model.gguf",
        )
    (private_dir / f"{case.id}-attempt1.txt").write_bytes(raw)
    result["predictions"][0]["attempts"][0]["error_type"] = "ForgedError"
    rows[3]["prediction"] = result["predictions"][0]
    journal.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    result["journal_sha256"] = hashlib.sha256(journal.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="raw-to-prediction replay differs"):
        auditor.verify(
            tmp_path / "protocol.json",
            write(result),
            journal,
            private_dir,
            tmp_path / "model.gguf",
        )


@pytest.mark.parametrize(
    "tamper",
    [
        lambda item: item["summary"]["counts"].__setitem__("fully_correct_cases", 1),
        lambda item: item["predictions"][1].__setitem__(
            "case_id", item["predictions"][0]["case_id"]
        ),
        lambda item: item["predictions"][0].__setitem__("raw_completion", "private text"),
        lambda item: item["predictions"][0]["attempts"][0].__setitem__(
            "error_type", "private prompt: hello"
        ),
        lambda item: item.__setitem__("protocol_sha256", "b" * 64),
    ],
)
def test_tampered_result_is_rejected(complete_result, tmp_path, tamper):
    result, write, journal, private_dir = complete_result
    changed = copy.deepcopy(result)
    tamper(changed)
    with pytest.raises((ValueError, TypeError)):
        auditor.verify(
            tmp_path / "protocol.json",
            write(changed),
            journal,
            private_dir,
            tmp_path / "model.gguf",
        )


@pytest.mark.parametrize("tamper", ("swap", "duplicate", "summary", "truncate"))
def test_journal_tampering_is_rejected(complete_result, tmp_path, tamper):
    result, write, journal, private_dir = complete_result
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    if tamper == "swap":
        rows[1], rows[3] = rows[3], rows[1]
    elif tamper == "duplicate":
        rows.insert(3, rows[1])
    elif tamper == "summary":
        rows[-1]["summary"]["counts"]["fully_correct_cases"] = 1
    else:
        rows.pop()
    journal.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    with pytest.raises(ValueError):
        auditor.verify(
            tmp_path / "protocol.json",
            write(result),
            journal,
            private_dir,
            tmp_path / "model.gguf",
        )


@pytest.mark.parametrize(
    "tamper",
    (
        "missing_restart",
        "oom",
        "unhealthy",
        "low_host_memory",
        "no_restart",
        "changed_container",
        "stale_final",
    ),
)
def test_server_boundary_tampering_is_rejected(complete_result, tmp_path, tamper):
    result, write, journal, private_dir = complete_result
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    boundary = next(
        index
        for index, row in enumerate(rows)
        if row.get("phase") == "after_restart" and row.get("completed_cases") == 8
    )
    if tamper == "missing_restart":
        rows.pop(boundary)
    elif tamper == "oom":
        rows[boundary]["oom_killed"] = True
    elif tamper == "unhealthy":
        rows[boundary]["healthy"] = False
    elif tamper == "low_host_memory":
        rows[boundary]["docker_host_memory_bytes"] = (
            auditor.RUNTIME["docker_host_min_memory_bytes"] - 1
        )
    elif tamper == "no_restart":
        rows[boundary]["started_at"] = rows[boundary - 1]["started_at"]
    elif tamper == "changed_container":
        rows[boundary]["container_id"] = "b" * 64
    else:
        rows[-2]["started_at"] = rows[1]["started_at"]
    journal.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    result["journal_sha256"] = hashlib.sha256(journal.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        auditor.verify(
            tmp_path / "protocol.json",
            write(result),
            journal,
            private_dir,
            tmp_path / "model.gguf",
        )


def test_duplicate_json_key_is_rejected():
    with pytest.raises(ValueError, match="duplicate JSON key"):
        auditor._strict_json(b'{"kind":"a","kind":"b"}')


def test_source_manifest_matches_runner_coverage():
    assert auditor._expected_source_paths() == set(baseline_runner.SOURCE_PATHS)


@pytest.mark.parametrize(
    "omitted",
    (
        "evals/structured_nlu/semantics.py",
        "llm/structured_output.py",
        "services/flow/professor/appointment/llm_structured.py",
    ),
)
def test_missing_model_source_is_rejected(tmp_path, monkeypatch, omitted):
    protocol = {
        "kind": auditor.PROTOCOL_KIND,
        "scope": auditor.SCOPE,
        "frozen_code_commit": "a" * 40,
        "input_hashes": {
            "dataset": hashlib.sha256(auditor.DATASET.read_bytes()).hexdigest(),
            "review_ledger": hashlib.sha256(auditor.LEDGER.read_bytes()).hexdigest(),
        },
        "source_manifest": {
            path: hashlib.sha256((auditor.ROOT / path).read_bytes()).hexdigest()
            for path in auditor._expected_source_paths()
            if path != omitted
        },
        "model_sha256": auditor.MODEL_SHA256,
        "server_image_digest": auditor.IMAGE_DIGEST,
        "request_policy": auditor.REQUEST,
        "local_runtime": auditor.RUNTIME,
        "case_order": list(auditor.CASE_ORDER),
    }
    monkeypatch.setattr(auditor, "_file_sha", lambda _path: auditor.MODEL_SHA256)
    monkeypatch.setattr(
        auditor, "_frozen", lambda _commit, relative: (auditor.ROOT / relative).read_bytes()
    )
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol), encoding="utf-8")
    with pytest.raises(ValueError, match="source manifest paths differ"):
        auditor.check_protocol(path, tmp_path / "model.gguf")
