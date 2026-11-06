"""Compare two committed analyzer revisions on one reviewed AI-authored corpus.

Both workers use one local model server and the same request settings. Cases
alternate baseline/candidate order. Raw prompts and completions are not saved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ("git", "-C", str(root), *args),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _worker(args: argparse.Namespace) -> None:
    # Source root must take precedence over this runner's checkout.
    source_root = str(args.source_root.resolve())
    sys.path.insert(0, source_root)
    from evals.structured_nlu.ai_heldout import AIHeldoutCase, AIHeldoutRequestPolicy
    from scripts.run_ai_heldout_pair import _run_case, prompt_revision_sha256

    policy = AIHeldoutRequestPolicy.model_validate_json(args.policy.read_bytes())
    print(json.dumps({"ready": True, "prompt_sha256": prompt_revision_sha256()}), flush=True)
    for line in sys.stdin:
        case = AIHeldoutCase.model_validate_json(line)
        prediction = _run_case(
            case,
            endpoint=args.endpoint,
            model_id="/models/kanana.gguf",
            policy=policy,
        )
        print(prediction.model_dump_json(), flush=True)


def _start_worker(source_root: Path, endpoint: str, policy: Path) -> subprocess.Popen[str]:
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
            "--endpoint",
            endpoint,
            "--policy",
            str(policy),
        ),
        cwd=source_root,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
    return json.loads(line)


def _run(args: argparse.Namespace) -> None:
    from evals.structured_nlu.ai_heldout import load_reviewed_ai_heldout
    from evals.structured_nlu.metrics import score_predictions
    from evals.structured_nlu.schema import CasePrediction
    from scripts.run_ai_heldout_pair import _loopback_endpoint

    root = Path(__file__).resolve().parents[1]
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol["kind"] != "ai_authored_code_revision_pair_protocol_v1":
        raise ValueError("unexpected protocol kind")
    if args.output.exists() or args.output.with_suffix(".partial.jsonl").exists():
        raise ValueError("result or partial result already exists")
    _git(root, "merge-base", "--is-ancestor", protocol["candidate_revision"], "HEAD")
    if _git(args.baseline_root, "rev-parse", "HEAD") != protocol["baseline_revision"]:
        raise ValueError("baseline revision differs from frozen protocol")
    if _git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("candidate tracked sources must be clean")
    if _git(args.baseline_root, "status", "--porcelain"):
        raise ValueError("baseline worktree must be clean")
    if _sha256(Path(__file__)) != protocol["runner_sha256"]:
        raise ValueError("runner differs from frozen protocol")
    if _sha256(args.model_path) != protocol["model_sha256"]:
        raise ValueError("model differs from frozen protocol")
    if _sha256(args.policy) != protocol["request_policy_sha256"]:
        raise ValueError("request settings differ from frozen protocol")
    reviewed = load_reviewed_ai_heldout(args.dataset, args.ledger)
    if reviewed.dataset_sha256 != protocol["dataset_sha256"]:
        raise ValueError("dataset differs from frozen protocol")
    if _sha256(args.ledger) != protocol["review_ledger_sha256"]:
        raise ValueError("review ledger differs from frozen protocol")
    protocol_relative = args.protocol.resolve().relative_to(root)
    _git(root, "cat-file", "-e", f"HEAD:{protocol_relative}")
    if (
        _git(root, "show", f"HEAD:{protocol_relative}")
        != args.protocol.read_text(encoding="utf-8").strip()
    ):
        raise ValueError("protocol bytes differ from committed version")
    endpoint = _loopback_endpoint(args.endpoint)
    workers = {
        "baseline": _start_worker(args.baseline_root, endpoint, args.policy),
        "candidate": _start_worker(root, endpoint, args.policy),
    }
    try:
        for role, worker in workers.items():
            assert worker.stdout is not None
            ready = json.loads(worker.stdout.readline())
            if ready != {
                "ready": True,
                "prompt_sha256": protocol[f"{role}_prompt_sha256"],
            }:
                raise ValueError(f"{role} prompt sources differ from frozen protocol")
        predictions: dict[str, list[CasePrediction]] = {"baseline": [], "candidate": []}
        partial = args.output.with_suffix(".partial.jsonl")
        with partial.open("x", encoding="utf-8") as file:
            for index, case in enumerate(reviewed.dataset.cases):
                order = (
                    ("baseline", "candidate")
                    if index % 2 == 0
                    else (
                        "candidate",
                        "baseline",
                    )
                )
                for role in order:
                    prediction = CasePrediction.model_validate(_call_worker(workers[role], case))
                    predictions[role].append(prediction)
                    file.write(
                        json.dumps({"role": role, "prediction": prediction.model_dump(mode="json")})
                        + "\n"
                    )
                    file.flush()
                    os.fsync(file.fileno())

        def slice_score(role: str, *, boundary: bool) -> dict:
            selected = tuple(
                case
                for case in reviewed.dataset.cases
                if ("hard_negative" in case.tags) == boundary
            )
            ids = {case.id for case in selected}
            values = tuple(
                prediction for prediction in predictions[role] if prediction.case_id in ids
            )
            return score_predictions(selected, values).to_dict()

        result = {
            "kind": "ai_authored_code_revision_pair_result_v1",
            "claim_scope": "single_owner_reviewed_ai_authored_32_case_evaluation",
            "protocol_sha256": _sha256(args.protocol),
            "dataset_sha256": reviewed.dataset_sha256,
            "baseline_revision": protocol["baseline_revision"],
            "candidate_revision": protocol["candidate_revision"],
            "model_sha256": protocol["model_sha256"],
            "baseline_scores": score_predictions(
                reviewed.dataset.cases, tuple(predictions["baseline"])
            ).to_dict(),
            "candidate_scores": score_predictions(
                reviewed.dataset.cases, tuple(predictions["candidate"])
            ).to_dict(),
            "boundary_baseline_scores": slice_score("baseline", boundary=True),
            "boundary_candidate_scores": slice_score("candidate", boundary=True),
            "in_scope_baseline_scores": slice_score("baseline", boundary=False),
            "in_scope_candidate_scores": slice_score("candidate", boundary=False),
            "predictions": {
                role: [prediction.model_dump(mode="json") for prediction in values]
                for role, values in predictions.items()
            },
        }
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        partial.unlink()
        print(
            "full exact",
            result["baseline_scores"]["counts"]["fully_correct_cases"],
            result["candidate_scores"]["counts"]["fully_correct_cases"],
            "of",
            len(reviewed.dataset.cases),
        )
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
    worker.add_argument("--endpoint", required=True)
    worker.add_argument("--policy", type=Path, required=True)
    run = sub.add_parser("run")
    run.add_argument("--baseline-root", type=Path, required=True)
    run.add_argument("--endpoint", required=True)
    run.add_argument("--model-path", type=Path, required=True)
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
