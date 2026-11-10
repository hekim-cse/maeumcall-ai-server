"""Independently verify the frozen RE/V two-stage comparison journal.

This verifier intentionally does not import the candidate implementation or
runner. It checks the finite saved decisions, journal order, conditional calls,
routes, source hashes, and comparison denominators without model access.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from scripts.probe_as_safety_clause_index import split_clauses, validate_indexed_evidence

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
SOURCES = {
    "runner_sha256": ROOT / "scripts/run_as_safety_staged_relation_development.py",
    "candidate_sha256": ROOT / "scripts/probe_as_safety_staged_relation.py",
    "baseline_sha256": ROOT / "scripts/probe_as_safety_clause_index.py",
    "baseline_route_sha256": ROOT / "scripts/probe_as_safety_evidence.py",
    "completion_sha256": ROOT / "scripts/as_safety_completion_v2.py",
    "container_check_sha256": ROOT / "scripts/run_as_safety_event_gate_fresh.py",
    "case_loader_sha256": ROOT / "scripts/run_as_safety_compact_relation_development.py",
    "result_verifier_sha256": Path(__file__),
    "re_dataset_sha256": DATA / "as-safety-relation-fresh-reviewed.v1.json",
    "v_dataset_sha256": DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
    "policy_sha256": DATA / "as-safety-grounded-development-request.v1.json",
}
DIRECT = "safety_action_required"
CONFIRM = "confirming_safety_status"
NORMAL = "collecting_service_request"
EVENT = {"observed", "uncertain", "nonoccurring", "none"}
RELATION = {
    "current_product",
    "current_part",
    "other_product",
    "location_only",
    "alternative_unknown",
    "unknown",
}
STAGE_FIELDS = {
    "called",
    "decision",
    "error_stage",
    "error_type",
    "finish_reason",
    "latency_ms",
    "skip_reason",
}
END_FIELDS = {
    "event",
    "case_id",
    "arm",
    "decision",
    "route",
    "error_stage",
    "error_type",
    "stage1",
    "stage2",
    "call_count",
    "latency_ms",
}


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _duration(value: object) -> bool:
    return type(value) in {int, float} and 0 <= value < 86_400_000


def _index(value: object, count: int, nullable: bool = True) -> bool:
    return (nullable and value is None) or (type(value) is int and 1 <= value <= count)


def _event(decision: object, count: int) -> None:
    if not isinstance(decision, dict) or set(decision) != {"event_index", "event_status"}:
        raise ValueError("event decision fields differ")
    index, status = decision["event_index"], decision["event_status"]
    if status not in EVENT or not _index(index, count) or (status == "none") != (index is None):
        raise ValueError("event decision values differ")


def _source(decision: object, count: int) -> None:
    if not isinstance(decision, dict) or set(decision) != {
        "product_index",
        "source_index",
        "source_relation",
    }:
        raise ValueError("source decision fields differ")
    product, source, relation = (
        decision["product_index"],
        decision["source_index"],
        decision["source_relation"],
    )
    if (
        not _index(product, count, False)
        or not _index(source, count)
        or relation not in RELATION
        or (relation != "unknown" and source is None)
    ):
        raise ValueError("source decision values differ")


def _stage(stage: object, *, skipped: str | None, count: int, kind: str) -> None:
    if not isinstance(stage, dict) or set(stage) != STAGE_FIELDS:
        raise ValueError("stage fields differ")
    if skipped is not None:
        if stage != {
            "called": False,
            "decision": None,
            "error_stage": None,
            "error_type": None,
            "finish_reason": None,
            "latency_ms": None,
            "skip_reason": skipped,
        }:
            raise ValueError("skipped stage differs")
        return
    if stage["called"] is not True or stage["skip_reason"] is not None:
        raise ValueError("stage call state differs")
    if not _duration(stage["latency_ms"]):
        raise ValueError("stage latency differs")
    if stage["finish_reason"] not in {None, "stop", "length"}:
        raise ValueError("stage finish reason differs")
    if stage["error_stage"] is None:
        if stage["error_type"] is not None or stage["finish_reason"] != "stop":
            raise ValueError("successful stage metadata differs")
        if kind == "baseline":
            validate_indexed_evidence(json.dumps(stage["decision"]), count)
        elif kind == "event":
            _event(stage["decision"], count)
        else:
            _source(stage["decision"], count)
    else:
        if stage["error_stage"] not in {"response", "contract"}:
            raise ValueError("stage error location differs")
        if not isinstance(stage["error_type"], str) or not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_]{0,63}", stage["error_type"]
        ):
            raise ValueError("stage error type differs")
        if stage["decision"] is not None:
            raise ValueError("failed stage has a decision")
        if stage["error_stage"] == "contract" and stage["finish_reason"] != "stop":
            raise ValueError("contract error lacks completion")


def _route_baseline(decision: dict) -> str:
    if decision["target"] == "current" and decision["assertion"] == "observed":
        return DIRECT
    if decision["target"] in {"current", "unknown"} and decision["assertion"] in {
        "observed",
        "uncertain",
    }:
        return CONFIRM
    return NORMAL


def _route_candidate(decision: dict) -> str:
    status, relation = decision["event_status"], decision["source_relation"]
    if status in {"none", "nonoccurring"} or relation == "other_product":
        return NORMAL
    if status == "observed" and relation in {"current_product", "current_part"}:
        return DIRECT
    return CONFIRM


def _end(row: dict, arm: str, message: str) -> None:
    if set(row) != END_FIELDS or row["event"] != "end" or row["arm"] != arm:
        raise ValueError("end row shape differs")
    count = len(split_clauses(message))
    first, second = row["stage1"], row["stage2"]
    _stage(first, skipped=None, count=count, kind="baseline" if arm == "baseline" else "event")
    if arm == "baseline":
        _stage(second, skipped="baseline_single_call", count=count, kind="source")
    elif first["decision"] is None:
        _stage(second, skipped="upstream_failure", count=count, kind="source")
    elif first["decision"]["event_status"] in {"none", "nonoccurring"}:
        _stage(second, skipped="no_active_event", count=count, kind="source")
    else:
        _stage(second, skipped=None, count=count, kind="source")
    if row["call_count"] != int(first["called"]) + int(second["called"]):
        raise ValueError("call count differs")
    if not _duration(row["latency_ms"]):
        raise ValueError("case latency differs")
    if arm == "baseline":
        expected = first["decision"]
    elif first["decision"] is None or (second["called"] and second["decision"] is None):
        expected = None
    elif not second["called"]:
        expected = {
            **first["decision"],
            "product_index": None,
            "source_index": None,
            "source_relation": "none",
        }
    else:
        expected = {**first["decision"], **second["decision"]}
    if row["decision"] != expected:
        raise ValueError("combined decision differs")
    expected_route = (
        None
        if expected is None
        else (_route_baseline(expected) if arm == "baseline" else _route_candidate(expected))
    )
    if row["route"] != expected_route:
        raise ValueError("saved route differs")
    failed = first if first["error_stage"] else second if second["error_stage"] else None
    expected_error = (
        ("stage1" if failed is first else "stage2") + "_" + failed["error_stage"]
        if failed
        else None
    )
    if row["error_stage"] != expected_error or row["error_type"] != (
        failed["error_type"] if failed else None
    ):
        raise ValueError("case error metadata differs")


def verify(protocol_path: Path, journal_path: Path) -> dict:
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    if (
        protocol.get("kind") != "as_safety_staged_exposed_development_v1"
        or protocol.get("claim_scope") != "already_exposed_ai_authored_development_only"
        or protocol.get("case_order") != "RE01-RE16,V01-V16"
        or protocol.get("pair_order") != "alternating"
        or protocol.get("retry_policy") != "no_retry_manual_audit_on_interruption"
        or protocol.get("endpoint") != "http://127.0.0.1:18081/v1/chat/completions"
        or protocol.get("server_image_digest")
        != "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
        or protocol.get("max_tokens") != 180
        or protocol.get("local_runtime")
        != {
            "host_port": 18081,
            "cpu_count": 2,
            "memory_bytes": 4 * 1024**3,
            "context_tokens": 4096,
            "threads": 2,
            "parallel_slots": 1,
        }
        or not isinstance(protocol.get("model_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", protocol["model_sha256"])
    ):
        raise ValueError("protocol scope differs")
    for key, path in SOURCES.items():
        if digest(path) != protocol.get(key):
            raise ValueError(f"frozen {key} differs")
    cases = [
        case
        for key in ("re_dataset_sha256", "v_dataset_sha256")
        for case in json.loads(SOURCES[key].read_text(encoding="utf-8"))["cases"]
    ]
    ids = [*(f"RE{n:02}" for n in range(1, 17)), *(f"V{n:02}" for n in range(1, 17))]
    if [case["id"] for case in cases] != ids:
        raise ValueError("case order differs")
    lines = journal_path.read_text(encoding="utf-8").splitlines()
    if len(lines) != 129:
        raise ValueError("pair journal row count differs")
    rows = [json.loads(line) for line in lines]
    if rows[0] != {
        "event": "header",
        "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
    }:
        raise ValueError("journal header differs")
    per_case = []
    cursor = 1
    for index, case in enumerate(cases):
        order = ("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline")
        pair = {}
        for arm in order:
            if rows[cursor] != {"event": "begin", "case_id": case["id"], "arm": arm}:
                raise ValueError("pair begin order differs")
            end = rows[cursor + 1]
            if end.get("case_id") != case["id"]:
                raise ValueError("pair end order differs")
            _end(end, arm, case["user_message"])
            pair[arm] = end
            cursor += 2
        per_case.append(
            {
                "id": case["id"],
                "gold": case["expected_route"],
                "baseline": pair["baseline"]["route"],
                "candidate": pair["candidate"]["route"],
                "baseline_error": pair["baseline"]["error_stage"],
                "candidate_error": pair["candidate"]["error_stage"],
                "baseline_latency_ms": pair["baseline"]["latency_ms"],
                "candidate_latency_ms": pair["candidate"]["latency_ms"],
                "candidate_call_count": pair["candidate"]["call_count"],
                "candidate_stage2_skipped": pair["candidate"]["stage2"]["skip_reason"],
            }
        )
    summary = {}
    for name, part in (("RE", per_case[:16]), ("V", per_case[16:]), ("all", per_case)):
        summary[name] = {
            "denominator": len(part),
            "baseline_correct": sum(row["baseline"] == row["gold"] for row in part),
            "candidate_correct": sum(row["candidate"] == row["gold"] for row in part),
            "baseline_errors": sum(row["baseline_error"] is not None for row in part),
            "candidate_errors": sum(row["candidate_error"] is not None for row in part),
            "candidate_model_calls": sum(row["candidate_call_count"] for row in part),
            "gold_routes": dict(Counter(row["gold"] for row in part)),
        }
    return {"summary": summary, "per_case": per_case}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.protocol, args.journal), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
