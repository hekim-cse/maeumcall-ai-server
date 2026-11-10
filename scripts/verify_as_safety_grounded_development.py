"""Independently recompute exposed grounded-development routes and denominators."""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from collections import Counter
from pathlib import Path

from scripts.probe_as_safety_clause_index import split_clauses, validate_indexed_evidence
from scripts.probe_as_safety_evidence import route_evidence
from scripts.verify_as_safety_pair_journal_v3 import verify_journal

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
DATASETS = (
    DATA / "as-safety-relation-fresh-reviewed.v1.json",
    DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
)
DIRECT = "safety_action_required"
CONFIRM = "confirming_safety_status"
NORMAL = "collecting_service_request"
DECISION_FIELDS = {
    "product_index",
    "hazard_index",
    "product_start",
    "product_end",
    "owner_start",
    "owner_end",
    "model_relation",
    "anchor_relation",
    "event_status",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized(anchor: str) -> str:
    return "".join(unicodedata.normalize("NFKC", anchor).lower().split())


def verify_candidate_decision(decision: dict, message: str) -> str:
    """Reconstruct exact quoted spans without depending on the candidate router."""
    if not isinstance(decision, dict) or set(decision) != DECISION_FIELDS:
        raise ValueError("candidate decision fields differ")
    clauses = split_clauses(message)
    indices = (decision["product_index"], decision["hazard_index"])
    if any(type(index) is not int or not 1 <= index <= len(clauses) for index in indices):
        raise ValueError("source index differs")
    product_clause, owner_clause = (clauses[index - 1] for index in indices)
    start, end = decision["product_start"], decision["product_end"]
    if (
        type(start) is not int
        or type(end) is not int
        or not 0 <= start < end <= len(product_clause)
    ):
        raise ValueError("product span differs")
    product = product_clause[start:end]
    owner_start, owner_end = decision["owner_start"], decision["owner_end"]
    if owner_start is None and owner_end is None:
        owner = None
    elif (
        type(owner_start) is int
        and type(owner_end) is int
        and 0 <= owner_start < owner_end <= len(owner_clause)
    ):
        owner = owner_clause[owner_start:owner_end]
    else:
        raise ValueError("hazard owner span differs")
    if owner is None:
        anchor_relation = "unknown"
    else:
        left, right = _normalized(product), _normalized(owner)
        if right in {"그제품", "이제품", "해당제품", "그것", "이것"}:
            anchor_relation = "unknown"
        elif left == right or (
            min(len(left), len(right)) >= 3 and (left in right or right in left)
        ):
            anchor_relation = "current"
        else:
            anchor_relation = "other"
    if decision["anchor_relation"] != anchor_relation:
        raise ValueError("saved anchor relation differs from source spans")
    model_relation, event = decision["model_relation"], decision["event_status"]
    if model_relation not in {"current", "other", "unknown"} or event not in {
        "observed",
        "uncertain",
        "nonoccurring",
    }:
        raise ValueError("candidate decision value differs")
    if event == "nonoccurring" or (model_relation == anchor_relation == "other"):
        return NORMAL
    if model_relation == anchor_relation == "current" and event == "observed":
        return DIRECT
    return CONFIRM


def verify(protocol_path: Path, journal_path: Path) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("kind") != "as_safety_grounded_exposed_development_v1":
        raise ValueError("development protocol differs")
    sources = {
        "executor_sha256": ROOT / "scripts/as_safety_pair_executor_v3.py",
        "verifier_sha256": ROOT / "scripts/verify_as_safety_pair_journal_v3.py",
        "preflight_sha256": ROOT / "scripts/as_safety_preflight_v3.py",
        "journal_shape_sha256": ROOT / "scripts/verify_as_safety_pair_journal_v2.py",
        "error_audit_sha256": ROOT / "scripts/audit_as_safety_pair_errors.py",
        "runner_sha256": ROOT / "scripts/run_as_safety_grounded_development.py",
        "re_dataset_sha256": DATASETS[0],
        "v_dataset_sha256": DATASETS[1],
        "grounded_sha256": ROOT / "scripts/probe_as_safety_grounded_attribution.py",
        "baseline_sha256": ROOT / "scripts/probe_as_safety_clause_index.py",
        "baseline_route_sha256": ROOT / "scripts/probe_as_safety_evidence.py",
        "completion_sha256": ROOT / "scripts/as_safety_completion_v2.py",
        "container_check_sha256": ROOT / "scripts/run_as_safety_event_gate_fresh.py",
        "policy_sha256": DATA / "as-safety-grounded-development-request.v1.json",
        "result_verifier_sha256": Path(__file__),
    }
    for key, path in sources.items():
        if digest(path) != protocol.get(key):
            raise ValueError(f"frozen {key} differs")
    cases = [
        case for path in DATASETS for case in json.loads(path.read_text(encoding="utf-8"))["cases"]
    ]
    if [case["id"] for case in cases] != [
        *(f"RE{index:02}" for index in range(1, 17)),
        *(f"V{index:02}" for index in range(1, 17)),
    ]:
        raise ValueError("development case order differs")
    verify_journal(journal_path, [case["id"] for case in cases], digest(protocol_path))
    events = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()]
    ends = {(row["case_id"], row["arm"]): row for row in events if row["event"] == "end"}
    rows = []
    for case in cases:
        pair = {arm: ends[(case["id"], arm)] for arm in ("baseline", "candidate")}
        for arm, record in pair.items():
            if record["decision"] is None:
                continue
            expected_route = (
                route_evidence(
                    validate_indexed_evidence(
                        json.dumps(record["decision"]), len(split_clauses(case["user_message"]))
                    )
                )
                if arm == "baseline"
                else verify_candidate_decision(record["decision"], case["user_message"])
            )
            if record["route"] != expected_route:
                raise ValueError("saved route differs from bounded decision")
        rows.append(
            {
                "id": case["id"],
                "gold": case["expected_route"],
                "baseline": pair["baseline"]["route"],
                "candidate": pair["candidate"]["route"],
                "baseline_error": pair["baseline"]["error_stage"],
                "candidate_error": pair["candidate"]["error_stage"],
                "candidate_decision": pair["candidate"]["decision"],
                "baseline_latency_ms": pair["baseline"]["latency_ms"],
                "candidate_latency_ms": pair["candidate"]["latency_ms"],
            }
        )
    summary = {}
    for name, part in (
        ("RE", rows[:16]),
        ("V", rows[16:]),
        ("all", rows),
    ):
        summary[name] = {
            "denominator": len(part),
            "baseline_correct": sum(row["baseline"] == row["gold"] for row in part),
            "candidate_correct": sum(row["candidate"] == row["gold"] for row in part),
            "baseline_errors": sum(row["baseline_error"] is not None for row in part),
            "candidate_errors": sum(row["candidate_error"] is not None for row in part),
            "gold_routes": dict(Counter(row["gold"] for row in part)),
        }
    return {"summary": summary, "per_case": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.protocol, args.journal), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
