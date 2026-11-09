"""Recheck the exposed RE development pair against frozen source and labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

from scripts.audit_as_safety_pair_errors import audit_error_semantics
from scripts.probe_as_safety_clause_index import split_clauses, validate_indexed_evidence
from scripts.probe_as_safety_entailment_v2 import route_entailment, validate_entailment
from scripts.probe_as_safety_evidence import route_evidence
from scripts.probe_as_safety_relation import route_relation, validate_relation
from scripts.verify_as_safety_pair_journal_v2 import verify_journal

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(dataset_path: Path, protocol_path: Path, journal_path: Path) -> dict:
    protocol = json.loads(protocol_path.read_text())
    dataset = json.loads(dataset_path.read_text())
    if protocol.get("kind") != "as_safety_entailment_exposed_development_v1":
        raise ValueError("protocol kind differs")
    if protocol.get("claim_scope") != "already_exposed_ai_authored_development_only":
        raise ValueError("claim scope differs")
    if (
        dataset.get("provenance") != "ai_authored"
        or dataset.get("review_status") != "owner_approved_for_exploration"
    ):
        raise ValueError("dataset provenance differs")
    for path, key in (
        (dataset_path, "dataset_sha256"),
        (
            ROOT / "evals/structured_nlu/data/ai_heldout/q4-q5-request-policy.v1.json",
            "policy_sha256",
        ),
        (ROOT / "scripts/run_as_safety_entailment_development.py", "runner_sha256"),
        (ROOT / "scripts/as_safety_pair_executor_v2.py", "executor_sha256"),
        (ROOT / "scripts/as_safety_completion_v2.py", "completion_sha256"),
        (ROOT / "scripts/verify_as_safety_pair_journal_v2.py", "verifier_sha256"),
        (ROOT / "scripts/probe_as_safety_clause_index.py", "baseline_sha256"),
        (ROOT / "scripts/probe_as_safety_evidence.py", "baseline_route_sha256"),
        (ROOT / "scripts/probe_as_safety_entailment_v2.py", "candidate_sha256"),
    ):
        if sha256(path) != protocol.get(key):
            raise ValueError(f"frozen {key} differs")
    cases = dataset["cases"]
    if len(cases) != 16 or [case["id"] for case in cases] != [
        f"RE{index:02}" for index in range(1, 17)
    ]:
        raise ValueError("case order differs")
    for index, case in enumerate(cases):
        clause_count = len(split_clauses(case["user_message"]))
        if clause_count != 2:
            raise ValueError("reviewed sentence count differs")
        gold = validate_relation(json.dumps(case["expected_relation"]), clause_count)
        if route_relation(gold) != case["expected_route"]:
            raise ValueError("reviewed gold route differs")
        expected_route = (
            "safety_action_required",
            "confirming_safety_status",
            "collecting_service_request",
            "collecting_service_request",
        )[index // 4]
        if case["expected_route"] != expected_route:
            raise ValueError("reviewed gold group differs")
    verify_journal(journal_path, [case["id"] for case in cases], sha256(protocol_path))
    events = [json.loads(line) for line in journal_path.read_text().splitlines()]
    audit_error_semantics(events)
    ends = {(event["case_id"], event["arm"]): event for event in events if event["event"] == "end"}
    summary = {}
    for group, start, stop in (
        ("confirmed_hazard", 0, 4),
        ("ambiguous_hazard", 4, 8),
        ("other_source", 8, 12),
        ("nonoccurring_hazard", 12, 16),
        ("all", 0, 16),
    ):
        part = cases[start:stop]
        counts = {"denominator": len(part)}
        for arm in ("baseline", "candidate"):
            rows = [ends[(case["id"], arm)] for case in part]
            for case, row in zip(part, rows, strict=True):
                if row["decision"] is not None:
                    clause_count = len(split_clauses(case["user_message"]))
                    decision = (
                        validate_indexed_evidence(json.dumps(row["decision"]), clause_count)
                        if arm == "baseline"
                        else validate_entailment(json.dumps(row["decision"]), clause_count)
                    )
                    expected = (
                        route_evidence(decision)
                        if arm == "baseline"
                        else route_entailment(decision)
                    )
                    if row["route"] != expected:
                        raise ValueError("result route differs from decision")
            counts[f"{arm}_correct"] = sum(
                row["route"] == case["expected_route"] for case, row in zip(part, rows, strict=True)
            )
            counts[f"{arm}_errors"] = sum(row["error_stage"] is not None for row in rows)
            counts[f"{arm}_median_ms"] = round(
                statistics.median(row["latency_ms"] for row in rows), 3
            )
        summary[group] = counts
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "protocol", "journal"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.dataset, args.protocol, args.journal), ensure_ascii=False))


if __name__ == "__main__":
    main()
