"""The small probe can be audited without a local model or Docker."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.as_safety_v2 import probe


def _case(case_id="RE03"):
    return {
        "id": case_id,
        "user_message": "전기포트에 불꽃이 났어요. 전기포트를 접수하고 싶어요.",
        "target": {"clause_index": 2, "quote": "전기포트"},
        "event_reference": {"clause_index": 1, "quote": "불꽃"},
        "subject_reference": {"clause_index": 1, "quote": "전기포트"},
        "owner_reference": {"clause_index": 1, "quote": "전기포트"},
    }


def test_six_fixed_pairs_alternate_order():
    assert len(probe.ORDER) == 12
    assert [(row["case_id"], row["method"]) for row in probe.ORDER] == [
        ("RE03", "quote"),
        ("RE03", "ids"),
        ("RE06", "ids"),
        ("RE06", "quote"),
        ("RE09", "quote"),
        ("RE09", "ids"),
        ("V01", "ids"),
        ("V01", "quote"),
        ("V04", "quote"),
        ("V04", "ids"),
        ("V07", "ids"),
        ("V07", "quote"),
    ]


def test_quote_probe_persists_raw_and_emits_only_hashes(tmp_path, monkeypatch):
    raw = json.dumps(
        {
            "event_span": {"clause_index": 1, "quote": "불꽃"},
            "subject_span": {"clause_index": 1, "quote": "전기포트"},
            "owner_span": {"clause_index": 1, "quote": "전기포트"},
            "owner_kind": "explicit",
        },
        ensure_ascii=False,
    )
    monkeypatch.setattr(
        probe,
        "post_json_completion",
        lambda *a, **k: SimpleNamespace(content=raw, finish_reason="stop"),
    )
    row = probe.call_probe(_case(), "quote", tmp_path, probe.RequestPolicy())
    assert row["status"] == "validated"
    assert row["reference_hits"] == {"event_span": True, "subject_span": True, "owner_span": True}
    assert row["raw_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    assert (tmp_path / "RE03-quote.raw.txt").read_text() == raw
    assert "불꽃" not in json.dumps(row, ensure_ascii=False)
    assert "전기포트" not in json.dumps(row, ensure_ascii=False)


def test_id_prompt_has_no_reviewed_ebc_and_coverage_is_offline(tmp_path, monkeypatch):
    captured = {}

    def fake_completion(messages, schema, *, policy):
        captured["messages"] = messages
        captured["schema"] = schema
        return SimpleNamespace(
            content=json.dumps(
                {"event_id": None, "subject_id": None, "owner_id": None, "owner_kind": "unresolved"}
            ),
            finish_reason="stop",
        )

    monkeypatch.setattr(probe, "post_json_completion", fake_completion)
    case = _case()
    case["event_reference"] = {"clause_index": 1, "quote": "REVIEW_ONLY_SECRET"}
    row = probe.call_probe(case, "ids", tmp_path, probe.RequestPolicy())
    assert row["status"] == "validated"
    assert row["candidate_coverage"]["denominator"] == 3
    assert "REVIEW_ONLY_SECRET" not in json.dumps(captured, ensure_ascii=False)
    assert "REVIEW_ONLY_SECRET" not in json.dumps(row, ensure_ascii=False)


def test_contract_error_keeps_raw_but_not_quote(tmp_path, monkeypatch):
    monkeypatch.setattr(
        probe,
        "post_json_completion",
        lambda *a, **k: SimpleNamespace(content='{"bad":"private"}', finish_reason="stop"),
    )
    row = probe.call_probe(_case(), "quote", tmp_path, probe.RequestPolicy())
    assert row["status"] == "contract_error"
    assert row["error_code"] == "fields_invalid"
    assert row["spans"] is None
    assert row["raw_bytes"] > 0
    assert "private" not in json.dumps(row)


def test_transport_error_has_no_raw_file(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise probe.TransportError("transport_network")

    monkeypatch.setattr(probe, "post_json_completion", fail)
    row = probe.call_probe(_case(), "quote", tmp_path, probe.RequestPolicy())
    assert row["status"] == "response_error"
    assert row["raw_sha256"] is None
    assert not list(tmp_path.iterdir())


def test_finish_length_is_included_in_denominator(tmp_path, monkeypatch):
    monkeypatch.setattr(
        probe,
        "post_json_completion",
        lambda *a, **k: SimpleNamespace(content='{"partial":true}', finish_reason="length"),
    )
    row = probe.call_probe(_case(), "quote", tmp_path, probe.RequestPolicy())
    assert row["status"] == "response_error"
    assert row["error_code"] == "finish_length"
    assert row["raw_bytes"] > 0


def test_runner_writes_twelve_begin_end_pairs(tmp_path, monkeypatch):
    model = tmp_path / "model"
    model.write_bytes(b"model")
    monkeypatch.setattr(
        probe,
        "load_probe_protocol",
        lambda protocol, model_path: ({"request_policy": probe.POLICY}, "p" * 64),
    )
    monkeypatch.setattr(probe, "verify_container", lambda *a: None)
    monkeypatch.setattr(
        probe,
        "load_development_cases",
        lambda **kwargs: [_case(case_id) for case_id in probe.CASE_IDS],
    )
    calls = []

    def fake_call(case, method, private_dir, policy):
        calls.append((case["id"], method))
        return {"case_id": case["id"], "method": method, "status": "response_error"}

    monkeypatch.setattr(probe, "call_probe", fake_call)
    journal = tmp_path / "journal.jsonl"
    private = tmp_path / "private"
    probe.run_probe(tmp_path / "protocol", model, private, journal, container="model")
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert rows[0]["expected_calls"] == 12
    assert len(rows) == 25
    assert calls == [(row["case_id"], row["method"]) for row in probe.ORDER]
    assert [row["event"] for row in rows[1:]] == ["begin", "end"] * 12
    assert private.stat().st_mode & 0o077 == 0
    assert journal.stat().st_mode & 0o077 == 0


def test_protocol_refuses_uncommitted_protocol(tmp_path, monkeypatch):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")
    source_relative = "experiments/as_safety_v2/probe.py"
    source_file = tmp_path / source_relative
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"frozen source")
    input_file = tmp_path / "input.json"
    input_file.write_bytes(b"frozen input")
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe, "INPUTS", {"fixture": input_file})
    protocol = {field: None for field in probe.PROTOCOL_FIELDS}
    protocol.update(
        {
            "kind": probe.KIND,
            "claim_scope": probe.SCOPE,
            "case_order": list(probe.CASE_IDS),
            "request_order": list(probe.ORDER),
            "frozen_code_commit": "a" * 40,
            "input_hashes": {"fixture": probe.digest(input_file.read_bytes())},
            "source_manifest": {source_relative: probe.digest(source_file.read_bytes())},
            "model_sha256": probe.digest_file(model),
            "server_image_digest": probe.IMAGE,
            "request_policy": probe.POLICY,
            "local_runtime": probe.RUNTIME,
            "retry_policy": "no_retry_manual_audit_on_interruption",
            "candidate_generation": probe.CANDIDATE_GENERATION,
            "selection_criteria": probe.SELECTION_CRITERIA,
            "private_output": "outside_repository_mode_0700_files_0600",
        }
    )
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    monkeypatch.setattr(probe, "_source_paths", lambda commit: set(protocol["source_manifest"]))
    monkeypatch.setattr(
        probe,
        "_committed",
        lambda commit, relative: (tmp_path / relative).read_bytes(),
    )
    git_calls = []

    def fake_git(*args):
        git_calls.append(args)
        assert args == ("show", "HEAD:protocol.json")
        return b"different committed protocol"

    monkeypatch.setattr(probe, "_git", fake_git)
    with pytest.raises(ValueError, match="^probe protocol must be committed$"):
        probe.load_probe_protocol(path, model)
    assert git_calls == [("show", "HEAD:protocol.json")]


def test_private_output_must_be_outside_repository(tmp_path):
    with pytest.raises(ValueError, match="outside repository"):
        probe.run_probe(
            Path("unused"),
            Path("unused"),
            probe.ROOT / "private",
            tmp_path / "journal.jsonl",
            container="unused",
        )
