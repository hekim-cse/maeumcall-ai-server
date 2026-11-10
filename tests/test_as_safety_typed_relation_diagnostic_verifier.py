"""Reject corrupt or privacy-leaking candidate-only diagnostic journals."""

import json
from pathlib import Path

import pytest

from scripts.verify_as_safety_typed_relation_diagnostic import digest, verify, verify_decision

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
SOURCES = {
    "runner_sha256": ROOT / "scripts/run_as_safety_typed_relation_diagnostic.py",
    "classifier_sha256": ROOT / "scripts/classify_as_safety_typed_relation_failure.py",
    "candidate_sha256": ROOT / "scripts/probe_as_safety_typed_relation.py",
    "frozen_adapter_sha256": ROOT / "scripts/run_as_safety_typed_relation_development.py",
    "completion_sha256": ROOT / "scripts/as_safety_completion_v2.py",
    "container_check_sha256": ROOT / "scripts/run_as_safety_event_gate_fresh.py",
    "result_verifier_sha256": ROOT / "scripts/verify_as_safety_typed_relation_diagnostic.py",
    "re_dataset_sha256": DATA / "as-safety-relation-fresh-reviewed.v1.json",
    "v_dataset_sha256": DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
    "policy_sha256": DATA / "as-safety-grounded-development-request.v1.json",
    "prior_journal_sha256": DATA / "as-safety-typed-relation-exposed-development-result.v1.jsonl",
}


def valid_decision() -> dict:
    """Return a finite decision; the journal verifier does not judge semantic truth."""
    return {
        "product_index": 1,
        "event_index": 1,
        "source_index": 1,
        "occurrence_index": 1,
        "source_relation": "current_product",
        "event_status": "observed",
    }


def fixture_files(tmp_path: Path) -> tuple[Path, Path, list[dict]]:
    """Create one complete synthetic journal with the frozen source digests."""
    protocol = {
        "kind": "as_safety_typed_relation_diagnostic_v1",
        "claim_scope": "already_exposed_ai_authored_diagnostic_replicate_only",
        "case_order": "RE01-RE16,V01-V16",
        "retry_policy": "no_retry_manual_audit_on_interruption",
        "endpoint": "http://127.0.0.1:18081/v1/chat/completions",
        "model_sha256": "644b04cde835d486df33c6d4d7552ba367fcb28802fe39b6b4bb9c60b9ab6f3d",
        "server_image_digest": "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35",
        "max_tokens": 180,
        "local_runtime": {
            "host_port": 18081,
            "cpu_count": 2,
            "memory_bytes": 4 * 1024**3,
            "context_tokens": 4096,
            "threads": 2,
            "parallel_slots": 1,
        },
        **{key: digest(path) for key, path in SOURCES.items()},
    }
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    rows = [{"event": "header", "protocol_sha256": digest(protocol_path)}]
    for case_id in [
        *(f"RE{i:02}" for i in range(1, 17)),
        *(f"V{i:02}" for i in range(1, 17)),
    ]:
        rows.append({"event": "begin", "case_id": case_id})
        rows.append(
            {
                "event": "end",
                "case_id": case_id,
                "decision": valid_decision(),
                "route": "safety_action_required",
                "reason_code": None,
                "finish_reason": "stop",
                "latency_ms": 1.0,
            }
        )
    journal_path = tmp_path / "journal.jsonl"
    write_rows(journal_path, rows)
    return protocol_path, journal_path, rows


def write_rows(path: Path, rows: list[dict]) -> None:
    """Write test-only structured records with no model text."""
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_complete_journal_has_32_candidate_calls(tmp_path: Path) -> None:
    """One call per exposed case is required and counted once."""
    protocol, journal, _ = fixture_files(tmp_path)
    assert verify(protocol, journal) == {
        "denominator": 32,
        "valid_routes": 32,
        "reason_counts": {},
        "route_counts": {"safety_action_required": 32},
    }


@pytest.mark.parametrize("mutation", ["raw_text", "route", "reason", "missing_end", "order"])
def test_tampering_or_raw_text_is_rejected(tmp_path: Path, mutation: str) -> None:
    """A changed route, count, order, or raw response cannot pass verification."""
    protocol, journal, rows = fixture_files(tmp_path)
    if mutation == "raw_text":
        rows[2]["raw_response"] = "private utterance"
    elif mutation == "route":
        rows[2]["route"] = "collecting_service_request"
    elif mutation == "reason":
        rows[2]["decision"] = None
        rows[2]["route"] = None
        rows[2]["reason_code"] = "free_text_reason"
    elif mutation == "missing_end":
        rows.pop()
    else:
        rows[1]["case_id"] = "V16"
    write_rows(journal, rows)
    with pytest.raises(ValueError):
        verify(protocol, journal)


def test_protocol_source_hash_change_is_rejected(tmp_path: Path) -> None:
    """A changed classifier digest cannot be represented as the frozen run."""
    protocol, journal, _ = fixture_files(tmp_path)
    payload = json.loads(protocol.read_text(encoding="utf-8"))
    payload["classifier_sha256"] = "0" * 64
    protocol.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="frozen classifier_sha256 differs"):
        verify(protocol, journal)


def test_failure_reason_is_counted_without_raw_content(tmp_path: Path) -> None:
    """A bounded classifier failure remains distinct from a scored route."""
    protocol, journal, rows = fixture_files(tmp_path)
    rows[2].update(
        decision=None,
        route=None,
        reason_code="missing_target",
        finish_reason="stop",
    )
    write_rows(journal, rows)
    result = verify(protocol, journal)
    assert result["valid_routes"] == 31
    assert result["reason_counts"] == {"missing_target": 1}


def test_decision_rejects_impossible_evidence() -> None:
    """Route recomputation refuses inconsistent evidence numbers and types."""
    with pytest.raises(ValueError):
        verify_decision({**valid_decision(), "product_index": True}, 2)
    with pytest.raises(ValueError):
        verify_decision({**valid_decision(), "source_index": None}, 2)
