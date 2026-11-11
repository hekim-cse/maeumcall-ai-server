"""Independent checks for a raw-to-effective cause diagnostic journal."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from scripts import verify_as_safety_grounded_entity_link_cause_diagnostic as verifier
from scripts.probe_as_safety_clause_index import split_clauses


@pytest.fixture(autouse=True)
def _allow_synthetic_protocol(monkeypatch):
    monkeypatch.setattr(verifier, "_require_committed", lambda _path: None)


def _protocol() -> dict:
    return {
        "kind": "as_safety_grounded_entity_link_cause_diagnostic_v2",
        "claim_scope": "already_exposed_ai_authored_cause_diagnostic_only",
        "case_order": "RE01-RE06,RE08-RE11,V01-V08,V10,V12,V14,V16",
        "endpoint": "http://127.0.0.1:18081/v1/chat/completions",
        "retry_policy": "no_retry_manual_audit_on_interruption",
        "max_tokens": 320,
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
                    "model_entity_link": link,
                    "anchor_status": "model_abstained" if link == "unresolved" else "accepted",
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
    assert result["summary"]["all"]["model_relation_correct"] == 21
    assert result["summary"]["all"]["anchor_status_counts"] == {
        "accepted": 21,
        "model_abstained": 1,
    }
    assert result["by_gold_relation"]["current"]["relation_correct"] == 15
    assert result["by_gold_relation"]["other"]["relation_correct"] == 6
    assert result["development_thresholds"]["met"] is True
    assert "user_message" not in json.dumps(result, ensure_ascii=False)
    assert "quote_sha256" not in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize("reason", sorted(verifier.REJECTED_ANCHORS))
def test_rejected_anchor_demotes_only_effective_link(tmp_path, reason):
    protocol_path, journal_path, rows = _journal(tmp_path)
    end = rows[2]
    end.update(
        {
            "model_entity_link": "same_or_part",
            "anchor_status": reason,
            "entity_link": "unresolved",
            "evidence_spans": [],
            "source_relation": "unknown",
            "route": "confirming_safety_status",
        }
    )
    journal_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    result = verifier.verify(protocol_path, journal_path)
    assert result["summary"]["all"]["model_relation_correct"] == 22
    assert result["summary"]["all"]["relation_correct"] == 21
    assert result["summary"]["all"]["model_unknown_outputs"] == 0
    assert result["summary"]["all"]["unknown_outputs"] == 1
    assert result["demoted_ids"] == ["RE01"]
    assert result["rejected_anchor_subtype_independently_reproducible"] is False


@pytest.mark.parametrize(
    ("model_link", "anchor_status", "effective_link"),
    [
        ("unresolved", "accepted", "unresolved"),
        ("same_or_part", "model_abstained", "unresolved"),
        ("same_or_part", "rejected_missing_owner", "same_or_part"),
        ("same_or_part", "not_evaluated", "same_or_part"),
        ("same_or_part", "invented", "same_or_part"),
    ],
)
def test_illegal_model_to_effective_transition_rejected(
    tmp_path, model_link, anchor_status, effective_link
):
    protocol_path, journal_path, rows = _journal(tmp_path)
    rows[2]["model_entity_link"] = model_link
    rows[2]["anchor_status"] = anchor_status
    rows[2]["entity_link"] = effective_link
    if effective_link == "unresolved":
        rows[2]["evidence_spans"] = []
    journal_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="anchor transition differs"):
        verifier.verify(protocol_path, journal_path)


def test_error_row_requires_unobserved_model_and_anchor(tmp_path):
    protocol_path, journal_path, rows = _journal(tmp_path)
    end = rows[2]
    end.update(
        {
            "model_entity_link": None,
            "anchor_status": "not_evaluated",
            "entity_link": None,
            "evidence_spans": [],
            "source_relation": None,
            "route": None,
            "error_stage": "response",
            "error_code": "transport_error",
            "finish_reason": None,
        }
    )
    journal_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    assert verifier.verify(protocol_path, journal_path)["summary"]["all"]["errors"] == 1
    end["model_entity_link"] = "same_or_part"
    journal_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="failure has decision"):
        verifier.verify(protocol_path, journal_path)


def test_nonfinite_status_shapes_are_rejected_as_validation_errors(tmp_path):
    protocol_path, journal_path, rows = _journal(tmp_path)
    rows[2]["anchor_status"] = []
    journal_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="anchor status type"):
        verifier.verify(protocol_path, journal_path)


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


def test_protocol_and_policy_must_use_isolated_320_token_setting(tmp_path, monkeypatch):
    protocol_path, journal_path, _ = _journal(tmp_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["max_tokens"] = 180
    raw = json.dumps(protocol).encode()
    protocol_path.write_bytes(raw)
    journal_lines = journal_path.read_text(encoding="utf-8").splitlines()
    journal_lines[0] = json.dumps(
        {"event": "header", "protocol_sha256": hashlib.sha256(raw).hexdigest()}
    )
    journal_path.write_text("\n".join(journal_lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="protocol differs"):
        verifier.verify(protocol_path, journal_path)

    policy_path = tmp_path / "wrong-policy.json"
    policy = json.loads(verifier.SOURCES["policy_sha256"].read_text(encoding="utf-8"))
    policy["max_tokens"] = 180
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    monkeypatch.setitem(verifier.SOURCES, "policy_sha256", policy_path)
    protocol_path, journal_path, _ = _journal(tmp_path)
    with pytest.raises(ValueError, match="request policy differs"):
        verifier.verify(protocol_path, journal_path)


def test_observed_current_miss_blocks_gate(tmp_path):
    protocol_path, journal_path, _ = _journal(tmp_path, {"V16": "unknown"})
    result = verifier.verify(protocol_path, journal_path)
    assert result["by_gold_relation"]["current"]["relation_correct"] == 15
    assert result["summary"]["current_observed"]["relation_correct"] == 12
    assert result["development_thresholds"]["met"] is False
