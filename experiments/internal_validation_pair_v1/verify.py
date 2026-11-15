"""Independent journal and private-raw replay for paired validation artifacts."""

from __future__ import annotations

import argparse
import json
import re
import stat
import subprocess
import sys
from pathlib import Path

from evals.structured_nlu.ai_heldout import AIHeldoutDataset
from evals.structured_nlu.metrics import score_predictions
from evals.structured_nlu.schema import CasePrediction
from experiments.internal_validation_pair_v1 import qualification as gate

SHA = re.compile(r"[0-9a-f]{64}\Z")
RESULT_KIND = "ai_reviewed_internal_validation_pair_v1_result"
RESULT_KEYS = {
    "kind",
    "scope",
    "protocol_sha256",
    "journal_sha256",
    "predictions",
    "verification_status",
}
RAW_KEYS = {"attempt", "status", "raw_sha256", "raw_bytes", "error_type"}
BOUNDARY_KEYS = {
    "event",
    "phase",
    "completed_cases",
    "running",
    "oom_killed",
    "exit_code",
    "restart_count",
    "container_id",
    "started_at",
    "docker_host_memory_bytes",
    "memory_usage",
    "healthy",
}


def _read_rows(path: Path) -> list[dict]:
    raw = path.read_bytes()
    if not raw.endswith(b"\n"):
        raise ValueError("journal ends with incomplete line")
    rows = [gate._strict_json(line) for line in raw.splitlines()]
    if not rows or any(type(row) is not dict for row in rows):
        raise ValueError("journal row format differs")
    return rows


def _boundary(row: dict, *, phase: str, completed: int, previous: dict | None) -> dict:
    if set(row) != BOUNDARY_KEYS or row["event"] != "server_boundary":
        raise ValueError("server boundary fields differ")
    if row["phase"] != phase or row["completed_cases"] != completed:
        raise ValueError("server boundary schedule differs")
    if (
        row["running"] is not True
        or row["healthy"] is not True
        or row["oom_killed"] is not False
        or row["exit_code"] != 0
    ):
        raise ValueError("unhealthy or OOM boundary")
    if (
        type(row["docker_host_memory_bytes"]) is not int
        or row["docker_host_memory_bytes"] < gate.LOCAL_RUNTIME["docker_host_min_memory_bytes"]
    ):
        raise ValueError("Docker host memory boundary differs")
    if (
        type(row["container_id"]) is not str
        or not SHA.fullmatch(row["container_id"])
        or type(row["started_at"]) is not str
        or not 0 < len(row["started_at"]) <= 64
        or type(row["memory_usage"]) is not str
        or re.fullmatch(r"[0-9.]+[KMGT]?i?B / [0-9.]+[KMGT]?i?B", row["memory_usage"]) is None
        or type(row["restart_count"]) is not int
        or row["restart_count"] < 0
    ):
        raise ValueError("server boundary identity differs")
    if previous is None:
        if row["restart_count"] != 0:
            raise ValueError("pre-run server restart count differs")
    elif phase == "after_restart":
        if (
            row["container_id"] != previous["container_id"]
            or row["started_at"] == previous["started_at"]
            or row["restart_count"] != previous["restart_count"] + 1
        ):
            raise ValueError("planned restart record differs")
    elif (
        row["container_id"] != previous["container_id"]
        or row["started_at"] != previous["started_at"]
        or row["restart_count"] != previous["restart_count"]
    ):
        raise ValueError("unplanned server restart recorded")
    return row


def _raw(attempts: object, private_dir: Path, arm: str, case_id: str) -> set[str]:
    if type(attempts) is not list or not 1 <= len(attempts) <= 2:
        raise ValueError("raw attempts differ")
    seen = set()
    for number, item in enumerate(attempts, 1):
        if (
            type(item) is not dict
            or set(item) != RAW_KEYS
            or item["attempt"] != number
            or item["status"] != "received"
            or item["error_type"] is not None
            or type(item["raw_sha256"]) is not str
            or not SHA.fullmatch(item["raw_sha256"])
            or type(item["raw_bytes"]) is not int
            or not 0 <= item["raw_bytes"] <= 1_000_000
        ):
            raise ValueError("raw attempt metadata differs")
        path = private_dir / f"{arm}-{case_id}-attempt{number}.txt"
        if (
            path.is_symlink()
            or not path.is_file()
            or stat.S_IMODE(path.stat().st_mode) != 0o600
            or gate._file_sha(path) != item["raw_sha256"]
            or path.stat().st_size != item["raw_bytes"]
        ):
            raise ValueError("private raw response differs")
        seen.add(path.name)
    return seen


def _replay(
    *,
    candidate_root: Path,
    arm_root: Path,
    arm: str,
    case_id: str,
    private_dir: Path,
    protocol: dict,
    attempts: list[dict],
    worktree_head: str,
) -> CasePrediction:
    payload = {
        "request_policy": protocol["request_policy"],
        "commit": protocol["arms"][arm]["commit"],
        "source_manifest": protocol["arms"][arm]["source_manifest"],
        "raw_attempts": attempts,
        "worktree_head": worktree_head,
    }
    process = subprocess.run(
        (
            sys.executable,
            str(candidate_root / "experiments/internal_validation_pair_v1/worker.py"),
            "--mode",
            "replay",
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
        timeout=120,
        cwd=arm_root,
    )
    if process.returncode != 0:
        raise ValueError(f"raw replay failed: {arm}/{case_id}")
    row = gate._strict_json(process.stdout.encode())
    if (
        type(row) is not dict
        or set(row) != {"status", "case_id", "arm", "prediction", "raw_attempts"}
        or row["status"] != "complete"
        or row["case_id"] != case_id
        or row["arm"] != arm
        or row["raw_attempts"] != attempts
    ):
        raise ValueError("raw replay metadata differs")
    return CasePrediction.model_validate(row["prediction"])


def _semantic_prediction(prediction: CasePrediction) -> list[dict]:
    return [
        {
            "contract_valid": item.contract_valid,
            "output": item.output.model_dump(mode="json") if item.output else None,
            "error_type": item.error_type,
        }
        for item in prediction.attempts
    ]


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


def verify(
    *,
    protocol_path: Path,
    baseline_root: Path,
    candidate_root: Path,
    model_path: Path,
    output: Path,
    journal: Path,
    private_dir: Path,
    receipt: Path,
) -> dict:
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
    if receipt.exists() or receipt.is_symlink():
        raise FileExistsError("verified receipt already exists")
    if (
        private_dir.is_symlink()
        or not private_dir.is_dir()
        or stat.S_IMODE(private_dir.stat().st_mode) != 0o700
    ):
        raise ValueError("private raw directory boundary differs")
    result = gate._strict_json(output.read_bytes())
    if type(result) is not dict or set(result) != RESULT_KEYS:
        raise ValueError("result fields differ")
    if (
        result["kind"] != RESULT_KIND
        or result["scope"] != gate.SCOPE
        or result["verification_status"] != "unverified"
        or result["protocol_sha256"] != protocol_sha
        or result["journal_sha256"] != gate._file_sha(journal)
    ):
        raise ValueError("result provenance differs")
    rows = _read_rows(journal)
    cursor = 0

    def take() -> dict:
        nonlocal cursor
        if cursor >= len(rows):
            raise ValueError("journal ended early")
        row = rows[cursor]
        cursor += 1
        return row

    worktree_heads = {
        "baseline": gate._git(baseline_root, "rev-parse", "HEAD").decode().strip(),
        "candidate": gate._git(candidate_root, "rev-parse", "HEAD").decode().strip(),
    }
    if take() != {
        "event": "header",
        "protocol_sha256": protocol_sha,
        "worktree_heads": worktree_heads,
    }:
        raise ValueError("journal header differs")
    previous = _boundary(take(), phase="initial", completed=0, previous=None)
    case_data = AIHeldoutDataset.model_validate_json(
        (candidate_root / gate.INPUT_PATHS["validation_dataset"]).read_bytes()
    )
    cases = case_data.cases
    if [case.id for case in cases] != protocol["case_order"]:
        raise ValueError("validation case order differs")
    predictions: dict[str, list[CasePrediction]] = {"baseline": [], "candidate": []}
    filenames: set[str] = set()
    count = 0
    for pair in protocol["pair_order"]:
        for arm in pair["arms"]:
            case_id = pair["case_id"]
            if take() != {"event": "begin", "case_id": case_id, "arm": arm}:
                raise ValueError("journal pair order differs")
            end = take()
            if (
                set(end) != {"event", "status", "case_id", "arm", "prediction", "raw_attempts"}
                or end["event"] != "end"
                or end["status"] != "complete"
                or end["case_id"] != case_id
                or end["arm"] != arm
            ):
                raise ValueError("journal completion differs")
            prediction = CasePrediction.model_validate(end["prediction"])
            if prediction.case_id != case_id or len(prediction.attempts) != len(
                end["raw_attempts"]
            ):
                raise ValueError("journal prediction differs")
            filenames.update(_raw(end["raw_attempts"], private_dir, arm, case_id))
            replay = _replay(
                candidate_root=candidate_root,
                arm_root={"baseline": baseline_root, "candidate": candidate_root}[arm],
                arm=arm,
                case_id=case_id,
                private_dir=private_dir,
                protocol=protocol,
                attempts=end["raw_attempts"],
                worktree_head=worktree_heads[arm],
            )
            if _semantic_prediction(prediction) != _semantic_prediction(replay):
                raise ValueError("recorded prediction differs from raw replay")
            predictions[arm].append(prediction)
            count += 1
            if count % gate.LOCAL_RUNTIME["restart_interval_arm_evaluations"] == 0 and count < 64:
                previous = _boundary(
                    take(), phase="before_restart", completed=count, previous=previous
                )
                previous = _boundary(
                    take(), phase="after_restart", completed=count, previous=previous
                )
    previous = _boundary(take(), phase="final", completed=64, previous=previous)
    if filenames != {item.name for item in private_dir.iterdir()}:
        raise ValueError("private raw file inventory differs")
    summaries = {
        arm: score_predictions(cases, tuple(values)).to_dict()
        for arm, values in predictions.items()
    }
    paired = _paired_counts(cases, predictions)
    if take() != {"event": "summary", "summaries": summaries, "paired_counts": paired}:
        raise ValueError("journal summary differs")
    if cursor != len(rows):
        raise ValueError("journal has trailing rows")
    expected = {
        "kind": RESULT_KIND,
        "scope": gate.SCOPE,
        "verification_status": "unverified",
        "protocol_sha256": protocol_sha,
        "journal_sha256": gate._file_sha(journal),
        "predictions": {
            arm: [p.model_dump(mode="json") for p in values] for arm, values in predictions.items()
        },
    }
    if result != expected:
        raise ValueError("public result differs from verified journal")
    verified = {
        "kind": "ai_reviewed_internal_validation_pair_v1_verified_receipt",
        "verification_status": "verified",
        "scope": gate.SCOPE,
        "cases": 32,
        "arm_evaluations": 64,
        "protocol_sha256": protocol_sha,
        "journal_sha256": result["journal_sha256"],
        "unverified_result_sha256": gate._file_sha(output),
        "summaries": summaries,
        "paired_counts": paired,
    }
    with receipt.open("x", encoding="utf-8") as stream:
        json.dump(verified, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    return verified


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
    args = parser.parse_args()
    print(
        json.dumps(
            verify(
                protocol_path=args.protocol,
                baseline_root=args.baseline_root,
                candidate_root=args.candidate_root,
                model_path=args.model_path,
                output=args.output,
                journal=args.journal,
                private_dir=args.private_dir,
                receipt=args.receipt,
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
