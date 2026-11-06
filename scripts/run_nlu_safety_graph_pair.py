"""Run a frozen, owner-reviewed A/S graph comparison against one local Q5 server.

The paired workers share a model server. Results contain graph states and
normalized validation attempts, never prompts or raw completions.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ("git", "-C", str(root), *args), check=True, capture_output=True, text=True
    ).stdout.strip()


def _worker(args: argparse.Namespace) -> None:
    # Import workflow and prompt sources from the requested revision. The probe
    # itself is a frozen, shared evaluation harness from the evaluation checkout.
    sys.path.insert(0, str(args.source_root.resolve()))
    from evals.structured_nlu.ai_heldout import AIHeldoutCase, AIHeldoutRequestPolicy
    from scripts.run_ai_heldout_pair import prompt_revision_sha256

    spec = importlib.util.spec_from_file_location("frozen_safety_probe", args.probe_path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load frozen graph probe")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    policy = AIHeldoutRequestPolicy.model_validate_json(args.policy.read_bytes())
    print(json.dumps({"ready": True, "prompt_sha256": prompt_revision_sha256()}), flush=True)
    for line in sys.stdin:
        case = AIHeldoutCase.model_validate_json(line)
        result = probe.run_graph_case(
            case,
            endpoint=args.endpoint,
            model_id="/models/kanana.gguf",
            policy=policy,
        )
        print(json.dumps(result, ensure_ascii=False), flush=True)


def _start_worker(
    source_root: Path,
    probe_path: Path,
    endpoint: str,
    policy: Path,
) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(source_root)
    return subprocess.Popen(
        (
            sys.executable,
            "-u",
            str(Path(__file__).resolve()),
            "worker",
            "--source-root",
            str(source_root),
            "--probe-path",
            str(probe_path),
            "--endpoint",
            endpoint,
            "--policy",
            str(policy),
        ),
        cwd=source_root,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1,
    )


def _call_worker(worker: subprocess.Popen[str], case) -> dict:
    assert worker.stdin is not None and worker.stdout is not None
    worker.stdin.write(case.model_dump_json() + "\n")
    worker.stdin.flush()
    line = worker.stdout.readline()
    if not line:
        raise RuntimeError(f"revision worker exited with code {worker.poll()}")
    result = json.loads(line)
    if result["case_id"] != case.id:
        raise ValueError("worker returned a different case")
    return result


def _summarize(cases, results: list[dict]) -> dict:
    by_id = {result["case_id"]: result for result in results}
    if len(by_id) != len(cases) or set(by_id) != {case.id for case in cases}:
        raise ValueError("result IDs do not match the frozen dataset")

    def group(start: int, stop: int) -> list[dict]:
        return [by_id[cases[index].id] for index in range(start, stop)]

    positive = group(0, 8)
    negative = group(8, 16)
    scope = group(16, 20)
    return {
        "safety_positive": {
            "denominator": 8,
            "entered_safety_state": sum(
                item["conversation_state"] == "safety_action_required" for item in positive
            ),
            "model_requests": sum(item["model_request_count"] for item in positive),
        },
        "safety_negative": {
            "denominator": 8,
            "incorrectly_entered_safety_state": sum(
                item["conversation_state"] == "safety_action_required" for item in negative
            ),
            "model_requests": sum(item["model_request_count"] for item in negative),
        },
        "out_of_scope": {
            "denominator": 4,
            "contract_pass": sum(
                bool(item["attempts"]) and item["attempts"][-1]["contract_valid"] for item in scope
            ),
            "unknown_action": sum(
                bool(item["attempts"])
                and item["attempts"][-1]["output"] is not None
                and item["attempts"][-1]["output"]["user_action"] == "unknown"
                for item in scope
            ),
            "model_requests": sum(item["model_request_count"] for item in scope),
        },
    }


def _run(args: argparse.Namespace) -> None:
    from evals.structured_nlu.ai_heldout import load_reviewed_ai_heldout
    from scripts.run_ai_heldout_pair import _loopback_endpoint
    from scripts.run_nlu_scope_revision_pair import _restart_container, _verify_container

    root = Path(__file__).resolve().parents[1]
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("kind") != "ai_authored_safety_graph_pair_protocol_v1":
        raise ValueError("unexpected graph pair protocol kind")
    if args.output.exists() or args.output.with_suffix(".partial.jsonl").exists():
        raise ValueError("result or partial result already exists")
    for role, revision in (
        ("baseline", args.baseline_root),
        ("candidate", args.candidate_root),
    ):
        if _git(revision, "rev-parse", "HEAD") != protocol[f"{role}_revision"]:
            raise ValueError(f"{role} revision differs from frozen protocol")
        if _git(revision, "status", "--porcelain"):
            raise ValueError(f"{role} worktree must be clean")
    if _git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("evaluation checkout must be clean")
    relative_protocol = args.protocol.resolve().relative_to(root)
    if _git(root, "show", f"HEAD:{relative_protocol}") != args.protocol.read_text().strip():
        raise ValueError("protocol differs from committed version")
    if _sha256(Path(__file__)) != protocol["runner_sha256"]:
        raise ValueError("runner differs from frozen protocol")
    probe_path = root / "scripts/probe_nlu_safety_graph.py"
    if _sha256(probe_path) != protocol["probe_sha256"]:
        raise ValueError("graph probe differs from frozen protocol")
    for path, key in (
        (args.model_path, "model_sha256"),
        (args.policy, "request_policy_sha256"),
        (args.dataset, "dataset_sha256"),
        (args.ledger, "review_ledger_sha256"),
    ):
        if _sha256(path) != protocol[key]:
            raise ValueError(f"{key} differs from frozen protocol")
    reviewed = load_reviewed_ai_heldout(
        args.dataset,
        args.ledger,
        expected_scenario_keys=frozenset({"고객센터:a/s 접수"}),
    )
    cases = reviewed.dataset.cases
    if len(cases) != 20 or [case.id[-4:] for case in cases] != [
        f"sc{number:02}" for number in range(1, 21)
    ]:
        raise ValueError("graph pair requires SC01–SC20 in order")
    if reviewed.dataset_sha256 != protocol["dataset_sha256"]:
        raise ValueError("reviewed dataset hash mismatch")
    endpoint = _loopback_endpoint(args.endpoint)
    if endpoint != "http://127.0.0.1:18081/v1/chat/completions":
        raise ValueError("endpoint differs from verified local container")
    _verify_container(args.container_name, protocol, args.model_path)
    workers = {
        "baseline": _start_worker(args.baseline_root, probe_path, endpoint, args.policy),
        "candidate": _start_worker(args.candidate_root, probe_path, endpoint, args.policy),
    }
    try:
        for role, worker in workers.items():
            assert worker.stdout is not None
            ready = json.loads(worker.stdout.readline())
            if ready != {"ready": True, "prompt_sha256": protocol[f"{role}_prompt_sha256"]}:
                raise ValueError(f"{role} prompt sources differ from frozen protocol")
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
        output = {
            "kind": "ai_authored_safety_graph_pair_result_v1",
            "claim_scope": "single_owner_reviewed_ai_authored_20_case_as_graph",
            "protocol_sha256": _sha256(args.protocol),
            "dataset_sha256": reviewed.dataset_sha256,
            "baseline_revision": protocol["baseline_revision"],
            "candidate_revision": protocol["candidate_revision"],
            "model_sha256": protocol["model_sha256"],
            "restarts_after_case": restarts_after_case,
            "summaries": {role: _summarize(cases, values) for role, values in results.items()},
            "results": results,
        }
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
        partial.unlink()
        print(json.dumps(output["summaries"], ensure_ascii=False))
    finally:
        for worker in workers.values():
            if worker.stdin:
                worker.stdin.close()
            if worker.poll() is None:
                worker.terminate()
            worker.wait(timeout=10)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    worker = sub.add_parser("worker")
    worker.add_argument("--source-root", type=Path, required=True)
    worker.add_argument("--probe-path", type=Path, required=True)
    worker.add_argument("--endpoint", required=True)
    worker.add_argument("--policy", type=Path, required=True)
    run = sub.add_parser("run")
    run.add_argument("--baseline-root", type=Path, required=True)
    run.add_argument("--candidate-root", type=Path, required=True)
    run.add_argument("--endpoint", required=True)
    run.add_argument("--model-path", type=Path, required=True)
    run.add_argument("--container-name", required=True)
    run.add_argument("--policy", type=Path, required=True)
    run.add_argument("--dataset", type=Path, required=True)
    run.add_argument("--ledger", type=Path, required=True)
    run.add_argument("--protocol", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "worker":
        _worker(args)
    else:
        _run(args)


if __name__ == "__main__":
    main()
