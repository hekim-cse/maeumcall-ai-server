"""Independent tests for the frozen symmetric entity-link journal."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from scripts import verify_as_safety_symmetric_link_development as verifier

RELATION_BY_LINK = {
    "same_or_part": "current",
    "distinct_item": "other",
    "unresolved": "unknown",
}
ROUTE_BY_RELATION_AND_EVENT = {
    ("current", "observed"): "safety_action_required",
    ("current", "uncertain"): "confirming_safety_status",
    ("other", "observed"): "collecting_service_request",
    ("other", "uncertain"): "collecting_service_request",
    ("unknown", "observed"): "confirming_safety_status",
    ("unknown", "uncertain"): "confirming_safety_status",
}


@pytest.fixture(autouse=True)
def _allow_synthetic_protocol(monkeypatch):
    monkeypatch.setattr(verifier, "_require_committed", lambda _path: None)


def _protocol() -> dict:
    return {
        "kind": "as_safety_symmetric_link_development_v1",
        "claim_scope": "already_exposed_ai_authored_oracle_development_only",
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
        "input_hashes": {key: verifier.digest(path) for key, path in verifier.INPUTS.items()},
        "source_manifest": {
            path: verifier.digest(verifier.ROOT / path)
            for path in verifier.expected_manifest_paths()
        },
    }


def _journal(tmp_path, predictions: dict[str, tuple[str, str]] | None = None):
    protocol_path = tmp_path / "protocol.json"
    raw = json.dumps(_protocol()).encode()
    protocol_path.write_bytes(raw)
    rows = [{"event": "header", "protocol_sha256": hashlib.sha256(raw).hexdigest()}]
    for case in verifier._reviewed_cases():
        answers = (predictions or {}).get(
            case["id"], ("yes", "no") if case["gold_relation"] == "current" else ("no", "yes")
        )
        link = (
            "same_or_part"
            if answers == ("yes", "no")
            else "distinct_item"
            if answers == ("no", "yes")
            else "unresolved"
        )
        relation = RELATION_BY_LINK[link]
        rows.extend(
            [
                {"event": "begin", "case_id": case["id"]},
                {
                    "event": "end",
                    "case_id": case["id"],
                    "same_or_part_answer": answers[0],
                    "distinct_item_answer": answers[1],
                    "entity_link": link,
                    "source_relation": relation,
                    "route": ROUTE_BY_RELATION_AND_EVENT[(relation, case["event_status"])],
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


def _write_journal(journal_path, rows):
    journal_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_manifest_covers_static_imports_missing_from_previous_protocol():
    paths = verifier.expected_manifest_paths()
    assert {
        "scripts/probe_as_safety_grounded_entity_link_v1.py",
        "scripts/probe_as_safety_entity_link_v1.py",
        "scripts/run_as_safety_compact_relation_development.py",
        "scripts/run_ai_heldout_pair.py",
        "scripts/probe_gguf_structured_nlu.py",
    } <= paths
    assert (
        "evals/structured_nlu/data/ai_heldout/as-safety-relation-fresh-reviewed.v1.json"
        not in paths
    )


def test_45_row_verification_and_gate(tmp_path):
    protocol_path, journal_path, _ = _journal(tmp_path)
    result = verifier.verify(protocol_path, journal_path)
    assert result["summary"]["all"]["denominator"] == 22
    assert result["summary"]["all"]["relation_correct"] == 22
    assert result["summary"]["current_observed"]["relation_correct"] == 13
    assert result["by_gold_relation"]["other"]["relation_correct"] == 6
    assert sum(pair["expected_flip_recovered"] for pair in result["contrast_pairs"]) == 3
    assert result["development_thresholds"]["met"] is True
    assert result["raw_model_output_independently_reproducible"] is False
    assert "user_message" not in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize(
    ("answers", "expected"),
    [
        (("yes", "no"), "same_or_part"),
        (("no", "yes"), "distinct_item"),
        (("yes", "yes"), "unresolved"),
        (("no", "no"), "unresolved"),
        (("uncertain", "no"), "unresolved"),
        (("no", "uncertain"), "unresolved"),
    ],
)
def test_symmetric_answer_transition(tmp_path, answers, expected):
    protocol_path, journal_path, _ = _journal(tmp_path, {"RE01": answers})
    result = verifier.verify(protocol_path, journal_path)
    assert result["per_case"][0]["predicted_entity_link"] == expected


@pytest.mark.parametrize(
    ("case_id", "answers", "expected_route"),
    [
        ("RE01", ("yes", "no"), "safety_action_required"),
        ("RE06", ("yes", "no"), "confirming_safety_status"),
        ("RE09", ("no", "yes"), "collecting_service_request"),
        ("RE10", ("no", "yes"), "collecting_service_request"),
        ("RE01", ("no", "no"), "confirming_safety_status"),
        ("RE05", ("no", "no"), "confirming_safety_status"),
    ],
)
def test_route_mapping_uses_independent_expected_values(tmp_path, case_id, answers, expected_route):
    protocol_path, journal_path, _ = _journal(tmp_path, {case_id: answers})
    result = verifier.verify(protocol_path, journal_path)
    case = next(row for row in result["per_case"] if row["id"] == case_id)
    assert case["predicted_route"] == expected_route


@pytest.mark.parametrize("field", ["same_or_part_answer", "distinct_item_answer"])
@pytest.mark.parametrize("answer", [" yes", "yes ", " "])
def test_answer_whitespace_is_rejected(tmp_path, field, answer):
    protocol_path, journal_path, rows = _journal(tmp_path)
    rows[2][field] = answer
    _write_journal(journal_path, rows)
    with pytest.raises(ValueError, match="nonfinite symmetric answer"):
        verifier.verify(protocol_path, journal_path)


def test_valid_error_row_increases_errors_and_blocks_gate(tmp_path):
    protocol_path, journal_path, rows = _journal(tmp_path)
    rows[2].update(
        {
            "same_or_part_answer": None,
            "distinct_item_answer": None,
            "entity_link": None,
            "source_relation": None,
            "route": None,
            "error_stage": "response",
            "error_code": "transport_error",
            "finish_reason": None,
        }
    )
    _write_journal(journal_path, rows)
    result = verifier.verify(protocol_path, journal_path)
    assert result["summary"]["all"]["denominator"] == 22
    assert result["summary"]["all"]["errors"] == 1
    assert result["development_thresholds"]["met"] is False


def test_retry_after_failed_case_with_same_id_is_rejected(tmp_path):
    protocol_path, journal_path, rows = _journal(tmp_path)
    rows[2].update(
        {
            "same_or_part_answer": None,
            "distinct_item_answer": None,
            "entity_link": None,
            "source_relation": None,
            "route": None,
            "error_stage": "response",
            "error_code": "transport_error",
            "finish_reason": None,
        }
    )
    rows[3]["case_id"] = "RE01"
    rows[4]["case_id"] = "RE01"
    _write_journal(journal_path, rows)
    with pytest.raises(ValueError, match="journal call order differs"):
        verifier.verify(protocol_path, journal_path)


@pytest.mark.parametrize(
    "mutation",
    ["answer", "link", "route", "header", "order", "extra", "duplicate", "row_count"],
)
def test_journal_mutation_rejected(tmp_path, mutation):
    protocol_path, journal_path, rows = _journal(tmp_path)
    changed = copy.deepcopy(rows)
    end = changed[2]
    if mutation == "answer":
        end["same_or_part_answer"] = "maybe"
    elif mutation == "link":
        end["entity_link"] = "distinct_item"
    elif mutation == "route":
        end["route"] = "collecting_service_request"
    elif mutation == "header":
        changed[0]["protocol_sha256"] = "0" * 64
    elif mutation == "order":
        changed[1]["case_id"] = "V01"
    elif mutation == "extra":
        end["raw_response"] = "secret"
    elif mutation == "duplicate":
        lines = journal_path.read_text(encoding="utf-8").splitlines()
        lines[2] = lines[2].replace(
            '"entity_link": "same_or_part"',
            '"entity_link": "distinct_item", "entity_link": "same_or_part"',
        )
        journal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        changed.pop()
    if mutation != "duplicate":
        journal_path.write_text(
            "\n".join(json.dumps(row) for row in changed) + "\n", encoding="utf-8"
        )
    with pytest.raises(ValueError):
        verifier.verify(protocol_path, journal_path)


def test_manifest_and_input_hash_tampering_rejected(tmp_path):
    protocol_path, journal_path, _ = _journal(tmp_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["source_manifest"].pop("scripts/probe_as_safety_grounded_entity_link_v1.py")
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest paths"):
        verifier.verify(protocol_path, journal_path)

    protocol_path, journal_path, _ = _journal(tmp_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["input_hashes"]["re_dataset"] = "0" * 64
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    with pytest.raises(ValueError, match="frozen input re_dataset"):
        verifier.verify(protocol_path, journal_path)


def test_observed_current_miss_and_other_abstain_block_gate(tmp_path):
    protocol_path, journal_path, _ = _journal(
        tmp_path, {"V16": ("uncertain", "no"), "V02": ("no", "no")}
    )
    result = verifier.verify(protocol_path, journal_path)
    assert result["summary"]["current_observed"]["relation_correct"] == 12
    assert result["by_gold_relation"]["other"]["relation_correct"] == 5
    assert result["summary"]["all"]["unknown_outputs"] == 2
    assert result["development_thresholds"]["met"] is False
