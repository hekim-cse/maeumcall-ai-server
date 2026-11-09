"""Run a frozen, paired A/S safety attribution exploration on local Q5."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from evals.structured_nlu.ai_heldout import AIHeldoutRequestPolicy
from scripts.probe_as_safety_clause_index import (
    PROMPT as BASE_PROMPT,
)
from scripts.probe_as_safety_clause_index import (
    evidence_schema,
    split_clauses,
    validate_indexed_evidence,
)
from scripts.probe_as_safety_evidence import post_constrained_completion, route_evidence
from scripts.probe_as_safety_relation import (
    PROMPT as RELATION_PROMPT,
)
from scripts.probe_as_safety_relation import (
    relation_schema,
    route_relation,
    validate_relation,
)
from scripts.run_ai_heldout_pair import _loopback_endpoint
from scripts.run_as_safety_event_gate_fresh import verify_container

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "http://127.0.0.1:18081/v1/chat/completions"
ROUTES = {"safety_action_required", "confirming_safety_status", "collecting_service_request"}
GROUPS = (
    ("confirmed_hazard", 0, 4),
    ("ambiguous_hazard", 4, 8),
    ("other_source", 8, 12),
    ("nonoccurring_hazard", 12, 16),
)


def digest(path: Path) -> str:
    """Hash the bytes used for one frozen input or source file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_reviewed(path: Path) -> tuple[list[dict], str]:
    """Accept exactly the owner-reviewed AI-authored RE01–RE16 dataset."""
    data = path.read_bytes()
    payload = json.loads(data)
    if set(payload) != {"kind", "provenance", "review_status", "reviewed_date", "cases"}:
        raise ValueError("reviewed dataset fields differ")
    if (
        payload["kind"] != "as_safety_relation_ai_reviewed_v1"
        or payload["provenance"] != "ai_authored"
        or payload["review_status"] != "owner_approved_for_exploration"
        or payload["reviewed_date"] != "2026-11-09"
    ):
        raise ValueError("reviewed dataset provenance differs")
    cases = payload["cases"]
    if not isinstance(cases, list) or len(cases) != 16:
        raise ValueError("expected 16 reviewed cases")
    expected_routes = (
        ["safety_action_required"] * 4
        + ["confirming_safety_status"] * 4
        + ["collecting_service_request"] * 8
    )
    for number, (case, expected_route) in enumerate(zip(cases, expected_routes, strict=True), 1):
        if not isinstance(case, dict) or set(case) != {
            "id",
            "user_message",
            "expected_route",
            "expected_relation",
        }:
            raise ValueError("reviewed case fields differ")
        if case["id"] != f"RE{number:02}" or case["expected_route"] != expected_route:
            raise ValueError("reviewed case order or route differs")
        message = case["user_message"]
        if not isinstance(message, str) or not message.strip() or len(message) > 1000:
            raise ValueError("reviewed message is empty or too long")
        clause_count = len(split_clauses(message))
        if clause_count != 2:
            raise ValueError("reviewed sentence count differs")
        gold = validate_relation(json.dumps(case["expected_relation"]), clause_count)
        if route_relation(gold) != expected_route:
            raise ValueError("reviewed relation and route disagree")
    return cases, hashlib.sha256(data).hexdigest()


def summarize(rows: list[dict]) -> dict:
    """Keep direct, confirmation, normal, and error counts per fixed group."""
    if len(rows) != 16:
        raise ValueError("paired result denominator differs")
    summary = {}
    for name, start, stop in GROUPS:
        part = rows[start:stop]
        summary[name] = {
            "denominator": len(part),
            "baseline_direct": sum(
                row["baseline_route"] == "safety_action_required" for row in part
            ),
            "baseline_confirm": sum(
                row["baseline_route"] == "confirming_safety_status" for row in part
            ),
            "baseline_normal": sum(
                row["baseline_route"] == "collecting_service_request" for row in part
            ),
            "baseline_errors": sum(row["baseline_error"] is not None for row in part),
            "relation_direct": sum(
                row["relation_route"] == "safety_action_required" for row in part
            ),
            "relation_confirm": sum(
                row["relation_route"] == "confirming_safety_status" for row in part
            ),
            "relation_normal": sum(
                row["relation_route"] == "collecting_service_request" for row in part
            ),
            "relation_errors": sum(row["relation_error"] is not None for row in part),
        }
    return summary


def run(args: argparse.Namespace) -> None:
    """Reject drift, alternate call order, and save no raw utterance or completion."""
    if args.output.exists() or args.output.with_suffix(".partial.jsonl").exists():
        raise ValueError("result or partial output already exists")
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("kind") != "as_safety_relation_pair_protocol_v1":
        raise ValueError("unexpected protocol kind")
    if protocol.get("claim_scope") != "ai_authored_owner_reviewed_targeted_exploration":
        raise ValueError("unexpected claim scope")
    if protocol.get("retry_policy") != "no_retry_error_recorded":
        raise ValueError("retry policy differs")
    if protocol.get("case_order") != "RE01-RE16" or protocol.get("pair_order") != "alternating":
        raise ValueError("case or pair order differs")
    if protocol.get("max_tokens") != 140:
        raise ValueError("request token limit differs")
    if subprocess.run(
        ("git", "status", "--porcelain", "--untracked-files=no"),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip():
        raise ValueError("evaluation checkout has tracked changes")
    relative = args.protocol.resolve().relative_to(ROOT)
    committed = subprocess.run(
        ("git", "show", f"HEAD:{relative}"), cwd=ROOT, check=True, capture_output=True
    ).stdout
    if committed != args.protocol.read_bytes():
        raise ValueError("protocol differs from committed version")
    for path, key in (
        (Path(__file__), "runner_sha256"),
        (ROOT / "scripts/probe_as_safety_relation.py", "relation_sha256"),
        (ROOT / "scripts/probe_as_safety_clause_index.py", "baseline_sha256"),
        (ROOT / "scripts/probe_as_safety_evidence.py", "evidence_probe_sha256"),
        (ROOT / "scripts/run_as_safety_event_gate_fresh.py", "container_check_sha256"),
        (ROOT / "scripts/verify_as_safety_relation_pair.py", "verifier_sha256"),
        (args.dataset, "dataset_sha256"),
        (args.policy, "policy_sha256"),
        (args.model_path, "model_sha256"),
    ):
        if digest(path) != protocol[key]:
            raise ValueError(f"{key} differs from frozen protocol")
    cases, dataset_digest = load_reviewed(args.dataset)
    if dataset_digest != protocol["dataset_sha256"]:
        raise ValueError("reviewed dataset digest differs")
    if _loopback_endpoint(args.endpoint) != ENDPOINT:
        raise ValueError("unexpected local endpoint")
    if protocol.get("local_runtime") != {
        "host_port": 18081,
        "cpu_count": 2,
        "memory_bytes": 4 * 1024**3,
        "context_tokens": 4096,
        "threads": 2,
        "parallel_slots": 1,
    }:
        raise ValueError("local runtime differs")
    verify_container(args.container_name, args.model_path)
    policy = AIHeldoutRequestPolicy.model_validate_json(args.policy.read_bytes()).model_copy(
        update={"max_tokens": 140}
    )
    if policy.server_image_digest != protocol["server_image_digest"]:
        raise ValueError("model server image digest differs")
    rows = []
    partial = args.output.with_suffix(".partial.jsonl")
    with partial.open("x", encoding="utf-8") as file:
        for index, case in enumerate(cases):
            clauses = split_clauses(case["user_message"])
            source = "\n".join(f"{number}. {clause}" for number, clause in enumerate(clauses, 1))
            order = ("baseline", "relation") if index % 2 == 0 else ("relation", "baseline")
            row = {"case_id": case["id"], "order": list(order), "clause_count": len(clauses)}
            for arm in order:
                started = time.perf_counter()
                decision = None
                error_type = None
                try:
                    raw = post_constrained_completion(
                        ENDPOINT,
                        "/models/kanana.gguf",
                        [
                            {
                                "role": "system",
                                "content": BASE_PROMPT if arm == "baseline" else RELATION_PROMPT,
                            },
                            {"role": "user", "content": source},
                        ],
                        policy,
                        schema=evidence_schema(len(clauses))
                        if arm == "baseline"
                        else relation_schema(len(clauses)),
                    )
                    decision = (
                        validate_indexed_evidence(raw, len(clauses))
                        if arm == "baseline"
                        else validate_relation(raw, len(clauses))
                    )
                except (OSError, TimeoutError, ValueError, KeyError, TypeError) as error:
                    error_type = type(error).__name__
                route = (
                    route_evidence(decision)
                    if decision and arm == "baseline"
                    else route_relation(decision)
                    if decision
                    else None
                )
                row[f"{arm}_decision"] = decision
                row[f"{arm}_route"] = route
                row[f"{arm}_error"] = error_type
                row[f"{arm}_latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
            rows.append(row)
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
            file.flush()
            os.fsync(file.fileno())
    result = {
        "kind": "as_safety_relation_pair_result_v1",
        "claim_scope": protocol["claim_scope"],
        "protocol_sha256": digest(args.protocol),
        "dataset_sha256": dataset_digest,
        "summary": summarize(rows),
        "rows": rows,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    partial.unlink()
    print(json.dumps(result["summary"], ensure_ascii=False))


def main() -> None:
    """Require explicit frozen local paths for the paired exploration."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "policy", "protocol", "output", "model-path"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--container-name", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
