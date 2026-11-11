"""Check independent verification of the frozen entity-link diagnostic."""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from types import SimpleNamespace

import pytest

from scripts import verify_as_safety_entity_link_diagnostic as verifier

ORIGINAL_REQUIRE_COMMITTED = verifier._require_committed


def _protocol() -> dict:
    return {
        "kind": "as_safety_entity_link_diagnostic_v1",
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


def _journal(tmp_path, *, predictions: dict[str, str] | None = None):
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
                },
            ]
        )
    journal_path = tmp_path / "journal.jsonl"
    journal_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return protocol_path, journal_path, rows


@pytest.fixture(autouse=True)
def _allow_synthetic_protocol(monkeypatch):
    monkeypatch.setattr(verifier, "_require_committed", lambda _path: None)


def test_reviewed_selection_and_strata():
    cases = verifier._reviewed_cases()
    assert tuple(case["id"] for case in cases) == verifier.CASE_IDS
    assert len(cases) == 22
    assert Counter((case["gold_relation"], case["event_status"]) for case in cases) == {
        ("current", "observed"): 13,
        ("current", "uncertain"): 3,
        ("other", "observed"): 5,
        ("other", "uncertain"): 1,
    }
    assert {case["id"]: case["gold_relation"] for case in cases}["V04"] == "current"
    assert {case["id"]: case["event_status"] for case in cases}["RE06"] == "uncertain"


def test_mapping_route_and_error_contract():
    case = verifier._reviewed_cases()[0]
    end = {
        "event": "end",
        "case_id": case["id"],
        "entity_link": "same_or_part",
        "source_relation": "current",
        "route": "safety_action_required",
        "error_stage": None,
        "error_code": None,
        "http_status": None,
        "finish_reason": "stop",
        "latency_ms": 1.25,
    }
    verifier._check_end(end, case)
    for link, relation, route in (
        ("distinct_item", "other", "collecting_service_request"),
        ("unresolved", "unknown", "confirming_safety_status"),
    ):
        changed = {**end, "entity_link": link, "source_relation": relation, "route": route}
        verifier._check_end(changed, case)
    with pytest.raises(ValueError, match="successful decision"):
        verifier._check_end({**end, "entity_link": "distinct_item"}, case)
    failure = {
        **end,
        "entity_link": None,
        "source_relation": None,
        "route": None,
        "error_stage": "response",
        "error_code": "transport_error",
        "finish_reason": None,
    }
    verifier._check_end(failure, case)
    with pytest.raises(ValueError, match="response exception"):
        verifier._check_end({**failure, "finish_reason": "stop"}, case)
    with pytest.raises(ValueError, match="failure has decision"):
        verifier._check_end({**failure, "entity_link": "unresolved"}, case)


def test_independent_45_row_audit_and_strict_gate(tmp_path):
    protocol_path, journal_path, _ = _journal(tmp_path, predictions={"RE05": "unknown"})
    result = verifier.verify(protocol_path, journal_path)
    assert result["claim_scope"] == "already_exposed_ai_authored_oracle_diagnostic_only"
    assert result["historical_comparison_allowed"] is False
    assert result["summary"]["all"]["denominator"] == 22
    assert result["summary"]["all"]["relation_correct"] == 21
    assert result["summary"]["current_observed"]["relation_correct"] == 13
    assert result["by_gold_relation"]["current"]["relation_correct"] == 15
    assert result["by_gold_relation"]["other"]["relation_correct"] == 6
    assert result["summary"]["all"]["unknown_outputs"] == 1
    assert result["summary"]["sensitivity_excluding_V03_V04"]["denominator"] == 20
    assert result["summary"]["sensitivity_excluding_RE06"]["denominator"] == 21
    assert sum(pair["expected_flip_recovered"] for pair in result["contrast_pairs"]) == 3
    assert result["development_thresholds"]["met"] is True


def test_observed_current_miss_blocks_gate_even_with_current_15_of_16(tmp_path):
    protocol_path, journal_path, _ = _journal(tmp_path, predictions={"V16": "unknown"})
    result = verifier.verify(protocol_path, journal_path)
    assert result["by_gold_relation"]["current"]["relation_correct"] == 15
    assert result["by_gold_relation"]["other"]["relation_correct"] == 6
    assert result["summary"]["current_observed"]["relation_correct"] == 12
    assert result["development_thresholds"]["met"] is False


@pytest.mark.parametrize(
    "mutation",
    ["duplicate", "nonfinite", "extra_field", "order", "link_mismatch", "route", "row_count"],
)
def test_journal_tampering_rejected(tmp_path, mutation):
    protocol_path, journal_path, rows = _journal(tmp_path)
    changed = copy.deepcopy(rows)
    if mutation in {"duplicate", "nonfinite"}:
        lines = journal_path.read_text(encoding="utf-8").splitlines()
        if mutation == "duplicate":
            lines[2] = lines[2].replace(
                '"entity_link": "same_or_part"',
                '"entity_link": "distinct_item", "entity_link": "same_or_part"',
            )
        else:
            lines[2] = lines[2].replace('"latency_ms": 1.25', '"latency_ms": NaN')
        journal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        if mutation == "extra_field":
            changed[2]["raw_response"] = "secret"
        elif mutation == "order":
            changed[1]["case_id"] = "V01"
        elif mutation == "link_mismatch":
            changed[2]["entity_link"] = "distinct_item"
        elif mutation == "route":
            changed[2]["route"] = "collecting_service_request"
        else:
            changed.pop()
        journal_path.write_text(
            "\n".join(json.dumps(row) for row in changed) + "\n", encoding="utf-8"
        )
    with pytest.raises(ValueError):
        verifier.verify(protocol_path, journal_path)


def test_source_hash_and_commit_guard(tmp_path, monkeypatch):
    protocol_path, journal_path, _ = _journal(tmp_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["candidate_sha256"] = "0" * 64
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    with pytest.raises(ValueError, match="frozen candidate"):
        verifier.verify(protocol_path, journal_path)
    monkeypatch.setattr(verifier, "_require_committed", ORIGINAL_REQUIRE_COMMITTED)
    monkeypatch.setattr(
        verifier.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(stdout=b"wrong")
    )
    with pytest.raises(ValueError, match="not committed"):
        verifier._require_committed(verifier.SOURCES["result_verifier_sha256"])
