"""Pair the frozen A/S safety confirmation candidate against the prior graph."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
from pathlib import Path

from evals.structured_nlu.ai_heldout import load_reviewed_ai_heldout
from scripts.run_ai_heldout_pair import _loopback_endpoint
from scripts.run_nlu_safety_graph_pair import _call_worker, _git, _sha256, _start_worker
from scripts.run_nlu_scope_revision_pair import _restart_container, _verify_container


def summarize(cases, results: list[dict]) -> dict:
    """Keep direct protection, confirmation, normal flow, errors, and cost separate."""
    if [row["case_id"] for row in results] != [case.id for case in cases]:
        raise ValueError("results differ from reviewed case order")
    if len(results) != 32:
        raise ValueError("the frozen safety comparison requires 12+8+12 cases")

    def summary(rows: list[dict]) -> dict:
        return {
            "denominator": len(rows),
            "direct_safety": sum(
                row["conversation_state"] == "safety_action_required" for row in rows
            ),
            "safety_confirmation": sum(
                row["conversation_state"] == "confirming_safety_status" for row in rows
            ),
            "normal_collection": sum(
                row["conversation_state"] == "collecting_service_request" for row in rows
            ),
            "extraction_requests": sum(row["model_request_count"] for row in rows),
            "focus_requests": sum(row["focus_request_count"] for row in rows),
            "graph_errors": sum(row["error_type"] is not None for row in rows),
            "median_graph_latency_ms": round(
                statistics.median(row["graph_latency_ms"] for row in rows), 3
            ),
        }

    return {
        "confirmed_hazard": summary(results[:12]),
        "ambiguous_hazard": summary(results[12:20]),
        "no_current_hazard": summary(results[20:]),
    }


def run(args: argparse.Namespace) -> None:
    """Verify every frozen input before alternating the two graph revisions."""
    root = Path(__file__).resolve().parents[1]
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("kind") != "ai_authored_safety_confirmation_pair_protocol_v1":
        raise ValueError("unexpected confirmation protocol kind")
    if args.output.exists() or args.output.with_suffix(".partial.jsonl").exists():
        raise ValueError("result or partial result already exists")
    for role, source_root in (
        ("baseline", args.baseline_root),
        ("candidate", args.candidate_root),
    ):
        if _git(source_root, "rev-parse", "HEAD") != protocol[f"{role}_revision"]:
            raise ValueError(f"{role} revision differs from protocol")
        if _git(source_root, "status", "--porcelain"):
            raise ValueError(f"{role} worktree is dirty")
    if _git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("evaluation checkout has tracked changes")
    relative_protocol = args.protocol.resolve().relative_to(root)
    if _git(root, "show", f"HEAD:{relative_protocol}") != args.protocol.read_text().strip():
        raise ValueError("protocol differs from committed version")
    probe_path = root / "scripts/probe_nlu_safety_confirmation_graph.py"
    worker_path = root / "scripts/run_nlu_safety_graph_pair.py"
    for path, key in (
        (Path(__file__), "runner_sha256"),
        (worker_path, "worker_sha256"),
        (probe_path, "probe_sha256"),
        (args.model_path, "model_sha256"),
        (args.policy, "request_policy_sha256"),
        (args.dataset, "dataset_sha256"),
        (args.ledger, "review_ledger_sha256"),
        (args.goals, "graph_goals_sha256"),
    ):
        if _sha256(path) != protocol[key]:
            raise ValueError(f"{key} differs from protocol")
    reviewed = load_reviewed_ai_heldout(
        args.dataset,
        args.ledger,
        expected_scenario_keys=frozenset({"고객센터:a/s 접수"}),
    )
    cases = reviewed.dataset.cases
    if len(cases) != 32 or [case.id[-4:] for case in cases] != [
        f"cf{number:02}" for number in range(1, 33)
    ]:
        raise ValueError("expected CF01–CF32 exactly once in order")
    if reviewed.dataset_sha256 != protocol["dataset_sha256"]:
        raise ValueError("reviewed dataset digest differs")
    goals = json.loads(args.goals.read_text(encoding="utf-8"))
    if goals["dataset_sha256"] != reviewed.dataset_sha256 or [
        goal["case_id"] for goal in goals["goals"]
    ] != [case.id for case in cases]:
        raise ValueError("graph goals differ from reviewed cases")
    endpoint = _loopback_endpoint(args.endpoint)
    if endpoint != "http://127.0.0.1:18081/v1/chat/completions":
        raise ValueError("unexpected endpoint")
    _verify_container(args.container_name, protocol, args.model_path)
    workers = {}
    try:
        for role, source_root in (
            ("baseline", args.baseline_root),
            ("candidate", args.candidate_root),
        ):
            workers[role] = _start_worker(source_root, probe_path, endpoint, args.policy)
        for role, worker in workers.items():
            assert worker.stdout is not None
            ready = json.loads(worker.stdout.readline())
            if ready != {"ready": True, "prompt_sha256": protocol[f"{role}_prompt_sha256"]}:
                raise ValueError(f"{role} prompt sources differ from protocol")
        results: dict[str, list[dict]] = {"baseline": [], "candidate": []}
        restarts_after_case: list[int] = []
        partial = args.output.with_suffix(".partial.jsonl")
        with partial.open("x", encoding="utf-8") as file:
            for index, case in enumerate(cases):
                order = ("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline")
                for role in order:
                    result = _call_worker(workers[role], case)
                    results[role].append(result)
                    file.write(
                        json.dumps({"role": role, "result": result}, ensure_ascii=False) + "\n"
                    )
                    file.flush()
                    os.fsync(file.fileno())
                batch_size = protocol["restart_every_cases"]
                if (index + 1) % batch_size == 0 and index + 1 < len(cases):
                    _restart_container(args.container_name, protocol, args.model_path)
                    restarts_after_case.append(index + 1)
        result = {
            "kind": "ai_authored_safety_confirmation_pair_result_v1",
            "claim_scope": "single_owner_reviewed_ai_authored_32_case_as_safety_stress",
            "protocol_sha256": _sha256(args.protocol),
            "dataset_sha256": reviewed.dataset_sha256,
            "graph_goals_sha256": _sha256(args.goals),
            "baseline_revision": protocol["baseline_revision"],
            "candidate_revision": protocol["candidate_revision"],
            "model_sha256": protocol["model_sha256"],
            "restarts_after_case": restarts_after_case,
            "summaries": {role: summarize(cases, values) for role, values in results.items()},
            "results": results,
        }
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        partial.unlink()
        print(json.dumps(result["summaries"], ensure_ascii=False))
    finally:
        for worker in workers.values():
            try:
                if worker.stdin:
                    worker.stdin.close()
                if worker.poll() is None:
                    worker.terminate()
                try:
                    worker.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    worker.kill()
                    worker.wait()
            except (OSError, subprocess.SubprocessError):
                # Preserve the evaluation error and continue cleaning peers.
                try:
                    if worker.poll() is None:
                        worker.kill()
                    worker.wait()
                except (OSError, subprocess.SubprocessError):
                    pass


def main() -> None:
    """Parse paths for one frozen paired run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--container-name", required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--goals", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
