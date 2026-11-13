"""Tamper tests for the independent paired Stage2 journal audit."""

from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from experiments.as_safety_v2 import verify_sources as source
from experiments.as_safety_v3 import verify as audit


def _case() -> dict:
    message = "접수할 전기포트가 고장났습니다. 토스터에서 불꽃이 났습니다."
    return {
        "id": "V02",
        "message": message,
        "clauses": source._clauses(message),
        "relation": "other",
        "event_status": "observed",
    }


def _row(tmp_path) -> tuple[dict, dict, dict]:
    case = _case()
    clauses = case["clauses"]
    raw = json.dumps(
        {
            "owner_to_target": "distinct",
            "hazard_owner_span": {"clause_index": 2, "quote": "토스터"},
        },
        ensure_ascii=False,
    )
    raw_path = tmp_path / "V02-stage2.json.txt"
    raw_path.write_text(raw, encoding="utf-8")
    raw_path.chmod(0o600)
    stage1 = {
        "called": True,
        "status": "validated",
        "spans": {
            "event_span": source._reference({"clause_index": 2, "quote": "불꽃"}, clauses),
            "subject_span": source._reference({"clause_index": 2, "quote": "토스터"}, clauses),
            "owner_span": source._reference({"clause_index": 2, "quote": "토스터"}, clauses),
        },
    }
    old = {"stage1": stage1, "stage2": {"status": "validated", "effective_relation": "other"}}
    row = {
        "event": "end",
        "case_id": "V02",
        "baseline_stage1": deepcopy(stage1),
        "stage2": {
            "called": True,
            "status": "validated",
            "skip_reason": None,
            "error_code": None,
            "error_field": None,
            "finish_reason": "stop",
            "latency_ms": 2.0,
            "raw_sha256": source.digest(raw.encode()),
            "raw_bytes": len(raw.encode()),
            "model_link": "distinct",
            "effective_relation": "other",
            "hazard_owner_span": source._reference({"clause_index": 2, "quote": "토스터"}, clauses),
        },
        "source_relation": "other",
        "stage2_elapsed_ms": 2.1,
    }
    return row, case, old


def test_raw_response_and_public_decision_match(tmp_path):
    row, case, old = _row(tmp_path)
    result = audit._check_end(row, case, old, tmp_path)
    assert result["candidate_relation"] == "other"
    assert result["baseline_relation"] == "other"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda row: row["stage2"].update(model_link="same", effective_relation="current"),
        lambda row: row["stage2"]["hazard_owner_span"].update(start=1),
        lambda row: row["stage2"].update(raw_bytes=1),
        lambda row: row["stage2"].update(called=False),
        lambda row: row.update(source_relation="current"),
        lambda row: row.update(user_message="private source leak"),
        lambda row: row.update(stage2_elapsed_ms=1.0),
    ],
)
def test_tampered_public_row_fails(tmp_path, mutation):
    row, case, old = _row(tmp_path)
    mutation(row)
    with pytest.raises(ValueError):
        audit._check_end(row, case, old, tmp_path)


def test_tampered_private_raw_fails(tmp_path):
    row, case, old = _row(tmp_path)
    (tmp_path / "V02-stage2.json.txt").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="private Stage2 raw"):
        audit._check_end(row, case, old, tmp_path)


def test_baseline_stage1_must_be_identical(tmp_path):
    row, case, old = _row(tmp_path)
    row["baseline_stage1"]["status"] = "contract_error"
    with pytest.raises(ValueError, match="paired journal end"):
        audit._check_end(row, case, old, tmp_path)


def test_skipped_case_keeps_stage1_failure_in_22_case_denominator(tmp_path):
    row, case, old = _row(tmp_path)
    old["stage1"].update(status="contract_error", spans=None)
    old["stage2"].update(status="skipped", effective_relation=None)
    row["baseline_stage1"] = deepcopy(old["stage1"])
    row["stage2"] = {
        "called": False,
        "status": "skipped",
        "skip_reason": "baseline_stage1_invalid",
        **{key: None for key in audit.STAGE2_KEYS - {"called", "status", "skip_reason"}},
    }
    row["source_relation"] = "unknown"
    row["stage2_elapsed_ms"] = None
    result = audit._check_end(row, case, old, tmp_path)
    assert result["eligible"] is False
    assert result["candidate_relation"] == "unknown"


def test_raw_contract_does_not_accept_missing_owner_or_duplicate_key():
    clauses = _case()["clauses"]
    with pytest.raises(source.ContractError) as missing:
        audit._raw_stage2('{"owner_to_target":"distinct","hazard_owner_span":null}', clauses)
    assert (missing.value.code, missing.value.field) == ("owner_required", "hazard_owner_span")
    with pytest.raises(source.ContractError) as duplicate:
        audit._raw_stage2(
            '{"owner_to_target":"same","owner_to_target":"distinct","hazard_owner_span":null}',
            clauses,
        )
    assert duplicate.value.code == "duplicate_key"


def test_source_manifest_must_cover_both_packages(monkeypatch):
    paths = {
        "experiments/as_safety_v2/run.py",
        "experiments/as_safety_v2/verify.py",
        "experiments/as_safety_v2/verify_journal.py",
        "experiments/as_safety_v3/relation.py",
        "experiments/as_safety_v3/run.py",
        "experiments/as_safety_v3/verify.py",
    }
    monkeypatch.setattr(
        audit.subprocess,
        "run",
        lambda *_args, **_kwargs: type("Result", (), {"stdout": "\n".join(paths)})(),
    )
    assert audit._source_paths("a" * 40) == paths
    paths.remove("experiments/as_safety_v3/relation.py")
    with pytest.raises(ValueError, match="incomplete"):
        audit._source_paths("a" * 40)


def test_frozen_manifest_rejects_current_source_or_input_drift(tmp_path, monkeypatch):
    relative_source = "experiments/as_safety_v3/verify.py"
    frozen = {name: b"frozen input" for name in audit.INPUTS.values()}
    frozen[relative_source] = b"frozen source"
    for name, raw in frozen.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    protocol = {
        "kind": audit.KIND,
        "claim_scope": audit.SCOPE,
        "case_order": source.CASE_ORDER,
        "frozen_code_commit": "a" * 40,
        "input_hashes": {key: source.digest(frozen[name]) for key, name in audit.INPUTS.items()},
        "source_manifest": {relative_source: source.digest(frozen[relative_source])},
        "model_sha256": audit.MODEL_SHA,
        "server_image_digest": audit.IMAGE,
        "request_policy": audit.POLICY,
        "local_runtime": audit.RUNTIME,
        "retry_policy": "no_retry_manual_audit_on_interruption",
        "private_output": "outside_repository_mode_0700_files_0600",
    }
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "_source_paths", lambda _commit: {relative_source})
    monkeypatch.setattr(audit, "_git", lambda _commit, name: frozen[name])
    monkeypatch.setattr(
        audit.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=protocol_path.read_bytes()),
    )
    audit._protocol(protocol_path)
    (tmp_path / relative_source).write_bytes(b"modified source")
    with pytest.raises(ValueError, match="source manifest differs"):
        audit._protocol(protocol_path)
    (tmp_path / relative_source).write_bytes(frozen[relative_source])
    (tmp_path / audit.INPUTS["baseline_journal"]).write_bytes(b"modified journal")
    with pytest.raises(ValueError, match="input manifest differs"):
        audit._protocol(protocol_path)
