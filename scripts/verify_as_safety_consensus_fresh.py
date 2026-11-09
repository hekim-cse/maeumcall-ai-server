"""Independently audit V01–V16 safety consensus against reviewed gold."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

from scripts.as_safety_consensus_v1 import CONFIRM, DIRECT, NORMAL, consensus_route
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
    if protocol.get("kind") != "as_safety_consensus_fresh_protocol_v1":
        raise ValueError("protocol kind differs")
    if protocol.get("claim_scope") != "ai_authored_owner_reviewed_targeted_exploration":
        raise ValueError("claim scope differs")
    if (
        dataset.get("provenance") != "ai_authored"
        or dataset.get("review_status") != "owner_approved_for_exploration"
    ):
        raise ValueError("reviewed provenance differs")
    for path, key in (
        (dataset_path, "dataset_sha256"),
        (
            ROOT / "evals/structured_nlu/data/ai_heldout/q4-q5-request-policy.v1.json",
            "policy_sha256",
        ),
        (ROOT / "scripts/run_as_safety_consensus_fresh.py", "runner_sha256"),
        (ROOT / "scripts/as_safety_pair_executor_v2.py", "executor_sha256"),
        (ROOT / "scripts/as_safety_completion_v2.py", "completion_sha256"),
        (ROOT / "scripts/verify_as_safety_pair_journal_v2.py", "journal_verifier_sha256"),
        (ROOT / "scripts/probe_as_safety_clause_index.py", "baseline_sha256"),
        (ROOT / "scripts/probe_as_safety_evidence.py", "baseline_route_sha256"),
        (ROOT / "scripts/probe_as_safety_relation.py", "relation_sha256"),
        (ROOT / "scripts/probe_as_safety_entailment_v2.py", "gold_contract_sha256"),
        (ROOT / "scripts/as_safety_consensus_v1.py", "consensus_sha256"),
    ):
        if sha256(path) != protocol.get(key):
            raise ValueError(f"frozen {key} differs")
    cases = dataset["cases"]
    if len(cases) != 16 or [case["id"] for case in cases] != [
        f"V{index:02}" for index in range(1, 17)
    ]:
        raise ValueError("case order differs")
    verify_journal(journal_path, [case["id"] for case in cases], sha256(protocol_path))
    events = [json.loads(line) for line in journal_path.read_text().splitlines()]
    audit_error_semantics(events)
    ends = {(event["case_id"], event["arm"]): event for event in events if event["event"] == "end"}
    per_case = []
    for case in cases:
        message = case["user_message"]
        count = len(split_clauses(message))
        if count != 2:
            raise ValueError("reviewed sentence count differs")
        gold = validate_relation(json.dumps(case["expected_relation"]), count)
        entailment_gold = validate_entailment(json.dumps(case["expected_entailment"]), count)
        if (
            route_relation(gold) != case["expected_route"]
            or route_entailment(entailment_gold) != case["expected_route"]
        ):
            raise ValueError("reviewed gold route differs")
        pair = {arm: ends[(case["id"], arm)] for arm in ("baseline", "candidate")}
        for arm, row in pair.items():
            if row["decision"] is None:
                continue
            bounded = (
                validate_indexed_evidence(json.dumps(row["decision"]), count)
                if arm == "baseline"
                else validate_relation(json.dumps(row["decision"]), count)
            )
            expected = route_evidence(bounded) if arm == "baseline" else route_relation(bounded)
            if row["route"] != expected:
                raise ValueError("model route differs from decision")
        per_case.append(
            {
                "case_id": case["id"],
                "gold": case["expected_route"],
                "baseline": pair["baseline"]["route"],
                "relation": pair["candidate"]["route"],
                "consensus": consensus_route(pair["baseline"]["route"], pair["candidate"]["route"]),
                "errors": sum(row["error_stage"] is not None for row in pair.values()),
                "pair_latency_ms": sum(row["latency_ms"] for row in pair.values()),
            }
        )
    groups = (
        ("current_hazard", (0, 2, 4, 6, 9, 11, 13, 15)),
        ("other_source", (1, 3, 5, 7)),
        ("uncertain_source", (8,)),
        ("nonoccurring", (10, 12, 14)),
        ("all", tuple(range(16))),
    )
    summary = {}
    for name, indices in groups:
        part = [per_case[index] for index in indices]
        counts = {"denominator": len(part), "arm_errors": sum(row["errors"] for row in part)}
        for arm in ("baseline", "relation", "consensus"):
            counts[f"{arm}_correct"] = sum(row[arm] == row["gold"] for row in part)
            counts[f"{arm}_direct"] = sum(row[arm] == DIRECT for row in part)
            counts[f"{arm}_confirm"] = sum(row[arm] == CONFIRM for row in part)
            counts[f"{arm}_normal"] = sum(row[arm] == NORMAL for row in part)
        counts["median_pair_latency_ms"] = round(
            statistics.median(row["pair_latency_ms"] for row in part), 3
        )
        summary[name] = counts
    return {"summary": summary, "per_case": per_case}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "protocol", "journal"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(verify(args.dataset, args.protocol, args.journal)["summary"], ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
