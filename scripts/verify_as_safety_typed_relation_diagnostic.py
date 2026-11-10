"""Independently audit a candidate-only, text-free RE/V diagnostic journal."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.probe_as_safety_clause_index import split_clauses

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
MODEL_SHA256 = "644b04cde835d486df33c6d4d7552ba367fcb28802fe39b6b4bb9c60b9ab6f3d"
IMAGE_SHA256 = "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
DATASETS = (
    DATA / "as-safety-relation-fresh-reviewed.v1.json",
    DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
)
FIELDS = {
    "product_index",
    "event_index",
    "source_index",
    "occurrence_index",
    "source_relation",
    "event_status",
}
RELATIONS = {
    "current_product",
    "current_part",
    "other_product",
    "location_only",
    "alternative_unknown",
    "unknown",
    "none",
}
STATUSES = {"observed", "uncertain", "nonoccurring", "none"}
ROUTES = {
    "safety_action_required",
    "confirming_safety_status",
    "collecting_service_request",
}
REASONS = {
    "json_syntax",
    "field_set",
    "index_type",
    "enum",
    "empty_event_conflict",
    "missing_target",
    "missing_event_or_occurrence",
    "missing_source",
    "bounded_decision",
    "response_failure",
    "response_incomplete",
    "other_contract",
}
END_FIELDS = {
    "event",
    "case_id",
    "decision",
    "route",
    "reason_code",
    "finish_reason",
    "latency_ms",
}


def digest(path: Path) -> str:
    """Return a file digest without reading prompt or response text into the journal."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_decision(decision: dict, clause_count: int) -> str:
    """Recompute the route from finite evidence without importing the candidate."""
    if not isinstance(decision, dict) or set(decision) != FIELDS:
        raise ValueError("diagnostic decision fields differ")
    for name in ("product_index", "event_index", "source_index", "occurrence_index"):
        value = decision[name]
        if value is not None and (type(value) is not int or not 1 <= value <= clause_count):
            raise ValueError("diagnostic evidence index differs")
    relation, status = decision["source_relation"], decision["event_status"]
    if relation not in RELATIONS or status not in STATUSES:
        raise ValueError("diagnostic decision enum differs")
    indices = tuple(
        decision[name]
        for name in ("product_index", "event_index", "source_index", "occurrence_index")
    )
    if relation == "none" or status == "none":
        if relation != status or any(index is not None for index in indices):
            raise ValueError("diagnostic empty event differs")
    elif (
        decision["product_index"] is None
        or decision["event_index"] is None
        or decision["occurrence_index"] is None
        or (relation != "unknown" and decision["source_index"] is None)
    ):
        raise ValueError("diagnostic evidence is incomplete")
    if status in {"none", "nonoccurring"} or relation == "other_product":
        return "collecting_service_request"
    if status == "observed" and relation in {"current_product", "current_part"}:
        return "safety_action_required"
    return "confirming_safety_status"


def verify(protocol_path: Path, journal_path: Path) -> dict:
    """Check frozen inputs, exact journal order/shape, and saved route integrity."""
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if (
        protocol.get("kind") != "as_safety_typed_relation_diagnostic_v1"
        or protocol.get("claim_scope") != "already_exposed_ai_authored_diagnostic_replicate_only"
        or protocol.get("case_order") != "RE01-RE16,V01-V16"
        or protocol.get("retry_policy") != "no_retry_manual_audit_on_interruption"
        or protocol.get("endpoint") != "http://127.0.0.1:18081/v1/chat/completions"
        or protocol.get("model_sha256") != MODEL_SHA256
        or protocol.get("server_image_digest") != IMAGE_SHA256
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
    ):
        raise ValueError("diagnostic protocol differs")
    sources = {
        "runner_sha256": ROOT / "scripts/run_as_safety_typed_relation_diagnostic.py",
        "classifier_sha256": ROOT / "scripts/classify_as_safety_typed_relation_failure.py",
        "candidate_sha256": ROOT / "scripts/probe_as_safety_typed_relation.py",
        "frozen_adapter_sha256": ROOT / "scripts/run_as_safety_typed_relation_development.py",
        "completion_sha256": ROOT / "scripts/as_safety_completion_v2.py",
        "container_check_sha256": ROOT / "scripts/run_as_safety_event_gate_fresh.py",
        "result_verifier_sha256": Path(__file__),
        "re_dataset_sha256": DATASETS[0],
        "v_dataset_sha256": DATASETS[1],
        "policy_sha256": DATA / "as-safety-grounded-development-request.v1.json",
        "prior_journal_sha256": DATA
        / "as-safety-typed-relation-exposed-development-result.v1.jsonl",
    }
    for key, path in sources.items():
        if digest(path) != protocol.get(key):
            raise ValueError(f"frozen {key} differs")
    cases = [
        case for path in DATASETS for case in json.loads(path.read_text(encoding="utf-8"))["cases"]
    ]
    expected_ids = [
        *(f"RE{i:02}" for i in range(1, 17)),
        *(f"V{i:02}" for i in range(1, 17)),
    ]
    if [case["id"] for case in cases] != expected_ids:
        raise ValueError("diagnostic case order differs")
    lines = journal_path.read_text(encoding="utf-8").splitlines()
    if len(lines) != 65:
        raise ValueError("diagnostic journal must contain 65 records")
    rows = [json.loads(line) for line in lines]
    if rows[0] != {"event": "header", "protocol_sha256": digest(protocol_path)}:
        raise ValueError("diagnostic journal header differs")
    reason_counts: Counter[str] = Counter()
    route_counts: Counter[str] = Counter()
    for position, case in enumerate(cases):
        case_id = expected_ids[position]
        if rows[2 * position + 1] != {"event": "begin", "case_id": case_id}:
            raise ValueError("diagnostic begin order differs")
        end = rows[2 * position + 2]
        if (
            not isinstance(end, dict)
            or set(end) != END_FIELDS
            or (end["event"] != "end" or end["case_id"] != case_id)
        ):
            raise ValueError("diagnostic end fields or order differ")
        latency = end["latency_ms"]
        if (
            isinstance(latency, bool)
            or not isinstance(latency, (int, float))
            or (not 0 <= latency < float("inf"))
        ):
            raise ValueError("diagnostic latency differs")
        reason, finish = end["reason_code"], end["finish_reason"]
        if reason is None:
            if finish != "stop" or end["route"] not in ROUTES:
                raise ValueError("diagnostic success metadata differs")
            route = verify_decision(end["decision"], len(split_clauses(case["user_message"])))
            if end["route"] != route:
                raise ValueError("diagnostic saved route differs")
            route_counts[route] += 1
        else:
            if reason not in REASONS or end["decision"] is not None or end["route"] is not None:
                raise ValueError("diagnostic error fields differ")
            if reason == "response_incomplete":
                if finish not in {"length", None}:
                    raise ValueError("diagnostic incomplete response differs")
            elif reason == "response_failure":
                if finish is not None:
                    raise ValueError("diagnostic response failure differs")
            elif finish != "stop":
                raise ValueError("diagnostic contract failure differs")
            reason_counts[reason] += 1
    return {
        "denominator": len(cases),
        "valid_routes": sum(route_counts.values()),
        "reason_counts": dict(reason_counts),
        "route_counts": dict(route_counts),
    }


def main() -> None:
    """Print the independently derived diagnostic counts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.protocol, args.journal), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
