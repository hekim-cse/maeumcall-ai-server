"""Run one frozen, paired Q5 validation experiment; never publish an official test score."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from evals.structured_nlu.ai_heldout import AIHeldoutDataset
from evals.structured_nlu.metrics import score_predictions
from evals.structured_nlu.schema import CasePrediction
from experiments.internal_validation_pair_v1 import qualification as gate
from experiments.nlu_current_baseline_v1 import run as server

RESULT_KIND = "ai_reviewed_internal_validation_pair_v1_result"


def _append(stream, row: dict) -> None:
    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def _boundary(
    stream, container_name: str, model_path: Path, protocol: dict, phase: str, count: int
) -> dict:
    row = server._server_boundary(
        stream, container_name, model_path, protocol, phase=phase, completed_cases=count
    )
    if row["restart_count"] != 0 and phase == "initial":
        raise ValueError("server restarted before validation")
    return row


def _identity(row: dict) -> tuple[str, str]:
    return row["container_id"], row["started_at"]


def _worker(
    *,
    protocol: dict,
    candidate_root: Path,
    arm_roots: dict[str, Path],
    private_dir: Path,
    arm: str,
    case_id: str,
    worktree_head: str,
) -> dict:
    candidate_root = candidate_root.resolve()
    arm_root = arm_roots[arm].resolve()
    private_dir = private_dir.resolve()
    payload = {
        "request_policy": protocol["request_policy"],
        "commit": protocol["arms"][arm]["commit"],
        "source_manifest": protocol["arms"][arm]["source_manifest"],
        "worktree_head": worktree_head,
    }
    result = subprocess.run(
        (
            sys.executable,
            str(candidate_root / "experiments/internal_validation_pair_v1/worker.py"),
            "--mode",
            "live",
            "--arm-root",
            str(arm_root),
            "--arm",
            arm,
            "--case-id",
            case_id,
            "--private-dir",
            str(private_dir),
        ),
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=600,
        cwd=arm_root,
    )
    if result.returncode not in (0, 2):
        raise ValueError(f"arm worker failed before a complete response: {arm}/{case_id}")
    row = gate._strict_json(result.stdout.encode())
    if type(row) is not dict or row.get("arm") != arm or row.get("case_id") != case_id:
        raise ValueError("arm worker identity differs")
    if result.returncode == 2 and row.get("status") == "completion_error":
        return row
    if result.returncode != 0 or row.get("status") != "complete":
        raise ValueError("arm worker status differs")
    return row


def _paired_counts(cases, predictions: dict[str, list[CasePrediction]]) -> dict[str, int]:
    counts = {"both_correct": 0, "baseline_only": 0, "candidate_only": 0, "both_incorrect": 0}
    for case, before, after in zip(
        cases, predictions["baseline"], predictions["candidate"], strict=True
    ):
        before_ok = score_predictions((case,), (before,)).counts.fully_correct_cases == 1
        after_ok = score_predictions((case,), (after,)).counts.fully_correct_cases == 1
        key = (
            "both_correct"
            if before_ok and after_ok
            else "baseline_only"
            if before_ok
            else "candidate_only"
            if after_ok
            else "both_incorrect"
        )
        counts[key] += 1
    return counts


def run(
    *,
    protocol_path: Path,
    baseline_root: Path,
    candidate_root: Path,
    model_path: Path,
    output: Path,
    journal: Path,
    private_dir: Path,
    receipt: Path,
    container_name: str,
) -> dict:
    """Require a fresh outside-worktree journal; an interrupted run is never resumed."""
    protocol_path = protocol_path.resolve()
    baseline_root = baseline_root.resolve()
    candidate_root = candidate_root.resolve()
    model_path = model_path.resolve()
    output = output.resolve()
    journal = journal.resolve()
    private_dir = private_dir.resolve()
    receipt = receipt.resolve()
    protocol, protocol_sha = gate.preflight(
        protocol_path=protocol_path,
        baseline_root=baseline_root,
        candidate_root=candidate_root,
        model_path=model_path,
        output=output,
        journal=journal,
        private_dir=private_dir,
        receipt=receipt,
    )
    if any(path.exists() or path.is_symlink() for path in (output, journal, private_dir, receipt)):
        raise FileExistsError("paired outputs already exist; interrupted runs require manual audit")
    observed = server.verify_container(container_name, model_path, protocol["local_runtime"])
    case_data = AIHeldoutDataset.model_validate_json(
        (candidate_root / gate.INPUT_PATHS["validation_dataset"]).read_bytes()
    )
    cases = case_data.cases
    if [case.id for case in cases] != protocol["case_order"]:
        raise ValueError("validation case order differs")
    private_dir.mkdir(mode=0o700)
    if stat.S_IMODE(private_dir.stat().st_mode) != 0o700:
        raise ValueError("private raw directory must be 0700")
    predictions: dict[str, list[CasePrediction]] = {"baseline": [], "candidate": []}
    arm_roots = {"baseline": baseline_root, "candidate": candidate_root}
    worktree_heads = {
        arm: gate._git(root, "rev-parse", "HEAD").decode().strip()
        for arm, root in arm_roots.items()
    }
    with journal.open("x", encoding="utf-8") as stream:
        _append(
            stream,
            {"event": "header", "protocol_sha256": protocol_sha, "worktree_heads": worktree_heads},
        )
        first = _boundary(stream, container_name, model_path, protocol, "initial", 0)
        if server._identity(observed) != _identity(first):
            raise ValueError("model server changed before initial boundary")
        identity = _identity(first)
        prior_restart_count = first["restart_count"]
        completed = 0
        for pair in protocol["pair_order"]:
            case_id = pair["case_id"]
            for arm in pair["arms"]:
                current = server.verify_container(
                    container_name, model_path, protocol["local_runtime"]
                )
                if (
                    server._identity(current) != identity
                    or current["RestartCount"] != prior_restart_count
                ):
                    raise ValueError("unplanned model server restart")
                _append(stream, {"event": "begin", "case_id": case_id, "arm": arm})
                row = _worker(
                    protocol=protocol,
                    candidate_root=candidate_root,
                    arm_roots=arm_roots,
                    private_dir=private_dir,
                    arm=arm,
                    case_id=case_id,
                    worktree_head=worktree_heads[arm],
                )
                _append(stream, {"event": "end", **row})
                if row["status"] != "complete":
                    raise ValueError("completion transport failed; paired score withheld")
                prediction = CasePrediction.model_validate(row["prediction"])
                if prediction.case_id != case_id:
                    raise ValueError("prediction case ID differs")
                predictions[arm].append(prediction)
                completed += 1
                if (
                    completed % protocol["local_runtime"]["restart_interval_arm_evaluations"] == 0
                    and completed < 64
                ):
                    before = _boundary(
                        stream, container_name, model_path, protocol, "before_restart", completed
                    )
                    if (
                        _identity(before) != identity
                        or before["restart_count"] != prior_restart_count
                    ):
                        raise ValueError("unplanned model server restart at boundary")
                    subprocess.run(
                        ("docker", "restart", "--time", "10", container_name),
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=150,
                    )
                    after = _boundary(
                        stream, container_name, model_path, protocol, "after_restart", completed
                    )
                    # Docker's RestartCount tracks automatic restarts; a manual
                    # `docker restart` changes StartedAt but leaves that count unchanged.
                    if (
                        before["container_id"] != after["container_id"]
                        or before["started_at"] == after["started_at"]
                        or after["restart_count"] != prior_restart_count
                    ):
                        raise ValueError("planned restart identity differs")
                    identity = _identity(after)
                    prior_restart_count = after["restart_count"]
        if completed != 64 or any(len(rows) != 32 for rows in predictions.values()):
            raise ValueError("paired run is incomplete")
        final = _boundary(stream, container_name, model_path, protocol, "final", completed)
        if _identity(final) != identity or final["restart_count"] != prior_restart_count:
            raise ValueError("unplanned model server restart before final boundary")
        summaries = {
            arm: score_predictions(cases, tuple(rows)).to_dict()
            for arm, rows in predictions.items()
        }
        paired = _paired_counts(cases, predictions)
        _append(stream, {"event": "summary", "summaries": summaries, "paired_counts": paired})
    result = {
        "kind": RESULT_KIND,
        "scope": gate.SCOPE,
        "verification_status": "unverified",
        "protocol_sha256": protocol_sha,
        "journal_sha256": gate._file_sha(journal),
        "predictions": {
            arm: [row.model_dump(mode="json") for row in rows] for arm, rows in predictions.items()
        },
    }
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in (
        "protocol",
        "baseline-root",
        "candidate-root",
        "model-path",
        "output",
        "journal",
        "private-dir",
        "receipt",
    ):
        parser.add_argument(f"--{flag}", type=Path, required=True)
    parser.add_argument("--container-name", required=True)
    args = parser.parse_args()
    run(
        protocol_path=args.protocol,
        baseline_root=args.baseline_root,
        candidate_root=args.candidate_root,
        model_path=args.model_path,
        output=args.output,
        journal=args.journal,
        private_dir=args.private_dir,
        receipt=args.receipt,
        container_name=args.container_name,
    )


if __name__ == "__main__":
    main()
