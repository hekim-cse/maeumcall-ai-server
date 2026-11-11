"""Independent checks for the frozen grounded entity-link journal contract."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from scripts import verify_as_safety_grounded_entity_link_diagnostic as verifier
from scripts.probe_as_safety_clause_index import split_clauses


@pytest.fixture(autouse=True)
def _allow_synthetic_protocol(monkeypatch):
    monkeypatch.setattr(verifier, "_require_committed", lambda _path: None)


def _protocol() -> dict:
    return {
        "kind": "as_safety_grounded_entity_link_diagnostic_v1",
        "claim_scope": "already_exposed_ai_authored_oracle_diagnostic_only",
        "case_order": "RE01-RE06,RE08-RE11,V01-V08,V10,V12,V14,V16",
        "endpoint": "http://127.0.0.1:18081/v1/chat/completions",
        "retry_policy": "no_retry_manual_audit_on_interruption",
        "max_tokens": 180,
        "local_runtime": {
            "host_port": 18081,
            "cpu_count": 2,
            "memory_bytes": 4 * 1024**3,
            "context_tokens": 4096,
            "threads": 2,
            "parallel_slots": 1,
        },
        "server_image_digest": (
            "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
        ),
        "model_repo_revision": "a" * 40,
        "model_sha256": "b" * 64,
        **{key: verifier.digest(path) for key, path in verifier.SOURCES.items()},
    }


def _evidence(case: dict) -> list[dict]:
    clauses = split_clauses(case["user_message"])
    indexes = dict.fromkeys((case["product_index"], case["owner_clause_index"]))
    return [
        {
            "clause_index": index,
            "start": 0,
            "end": len(clauses[index - 1]),
            "quote_sha256": hashlib.sha256(clauses[index - 1].encode("utf-8")).hexdigest(),
        }
        for index in indexes
    ]


def _journal(tmp_path, predictions: dict[str, str] | None = None):
    protocol_path = tmp_path / "protocol.json"
    raw = json.dumps(_protocol()).encode()
    protocol_path.write_bytes(raw)
    rows = [{"event": "header", "protocol_sha256": hashlib.sha256(raw).hexdigest()}]
    for case in verifier._reviewed_cases():
        relation = (predictions or {}).get(case["id"], case["gold_relation"])
        link = {"current": "same_or_part", "other": "distinct_item", "unknown": "unresolved"}[
            relation
        ]
        rows.extend(
            [
                {"event": "begin", "case_id": case["id"]},
                {
                    "event": "end",
                    "case_id": case["id"],
                    "entity_link": link,
                    "source_relation": relation,
                    "route": verifier._route(relation, case["event_status"]),
                    "error_stage": None,
                    "error_code": None,
                    "http_status": None,
                    "finish_reason": "stop",
                    "latency_ms": 1.25,
                    "evidence_spans": [] if link == "unresolved" else _evidence(case),
                },
            ]
        )
    journal_path = tmp_path / "journal.jsonl"
    journal_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return protocol_path, journal_path, rows


def test_reviewed_selection_and_strict_gate(tmp_path):
    protocol_path, journal_path, _ = _journal(tmp_path, {"RE05": "unknown"})
    result = verifier.verify(protocol_path, journal_path)
    assert result["summary"]["all"]["denominator"] == 22
    assert result["summary"]["all"]["relation_correct"] == 21
    assert result["by_gold_relation"]["current"]["relation_correct"] == 15
    assert result["by_gold_relation"]["other"]["relation_correct"] == 6
    assert result["development_thresholds"]["met"] is True
    assert "user_message" not in json.dumps(result, ensure_ascii=False)
    assert "quote_sha256" not in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize(
    "mutation",
    [
        "offset",
        "hash",
        "clause",
        "coverage",
        "empty",
        "extra",
        "duplicate",
        "order",
        "header",
        "route",
        "row_count",
    ],
)
def test_evidence_and_journal_tampering_rejected(tmp_path, mutation):
    protocol_path, journal_path, rows = _journal(tmp_path)
    changed = copy.deepcopy(rows)
    end = changed[2]
    evidence = end["evidence_spans"]
    if mutation == "offset":
        evidence[0]["end"] -= 1
    elif mutation == "hash":
        evidence[0]["quote_sha256"] = "0" * 64
    elif mutation == "clause":
        evidence[0]["clause_index"] = 999
    elif mutation == "coverage":
        evidence.pop()
    elif mutation == "empty":
        evidence.clear()
    elif mutation == "extra":
        end["raw_response"] = "secret"
    elif mutation == "duplicate":
        lines = journal_path.read_text(encoding="utf-8").splitlines()
        lines[2] = lines[2].replace(
            '"entity_link": "same_or_part"',
            '"entity_link": "same_or_part", "entity_link": "same_or_part"',
        )
        journal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        if mutation == "order":
            changed[1]["case_id"] = "V01"
        elif mutation == "header":
            changed[0]["protocol_sha256"] = "0" * 64
        elif mutation == "route":
            end["route"] = "collecting_service_request"
        else:
            changed.pop()
    if mutation != "duplicate":
        journal_path.write_text(
            "\n".join(json.dumps(row) for row in changed) + "\n", encoding="utf-8"
        )
    with pytest.raises(ValueError):
        verifier.verify(protocol_path, journal_path)


def test_unresolved_and_errors_cannot_carry_evidence(tmp_path):
    protocol_path, journal_path, rows = _journal(tmp_path, {"RE01": "unknown"})
    rows[2]["evidence_spans"] = _evidence(verifier._reviewed_cases()[0])
    journal_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unresolved or failed decision has evidence"):
        verifier.verify(protocol_path, journal_path)


def test_source_hash_mismatch_rejected(tmp_path):
    protocol_path, journal_path, _ = _journal(tmp_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["candidate_sha256"] = "0" * 64
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    with pytest.raises(ValueError, match="frozen candidate"):
        verifier.verify(protocol_path, journal_path)


def test_observed_current_miss_blocks_gate(tmp_path):
    protocol_path, journal_path, _ = _journal(tmp_path, {"V16": "unknown"})
    result = verifier.verify(protocol_path, journal_path)
    assert result["by_gold_relation"]["current"]["relation_correct"] == 15
    assert result["summary"]["current_observed"]["relation_correct"] == 12
    assert result["development_thresholds"]["met"] is False
