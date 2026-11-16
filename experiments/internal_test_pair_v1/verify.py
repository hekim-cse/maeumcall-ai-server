"""Independent journal and private-raw replay for paired internal test artifacts."""

from __future__ import annotations

import argparse
import json
import random
import re
import stat
import subprocess
import sys
from pathlib import Path

from evals.structured_nlu.ai_heldout import AIHeldoutDataset
from evals.structured_nlu.metrics import score_predictions
from evals.structured_nlu.schema import CasePrediction
from experiments.internal_test_pair_v1 import qualification as gate

SHA = re.compile(r"[0-9a-f]{64}\Z")
RESULT_KIND = "ai_reviewed_internal_test_pair_v1_result"
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
        # A planned manual restart changes StartedAt without incrementing
        # Docker's automatic RestartCount.
        if (
            row["container_id"] != previous["container_id"]
            or row["started_at"] == previous["started_at"]
            or row["restart_count"] != previous["restart_count"]
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
    dataset_key: str,
    dataset_relative: Path,
) -> CasePrediction:
    payload = {
        "request_policy": protocol["request_policy"],
        "commit": protocol["arms"][arm]["commit"],
        "source_manifest": protocol["arms"][arm]["source_manifest"],
        "raw_attempts": attempts,
        "worktree_head": worktree_head,
        "data_root": str(candidate_root),
        "data_commit": protocol["input_commit"],
        "dataset_sha256": protocol["inputs"][dataset_key],
        "dataset_relative": dataset_relative.as_posix(),
    }
    process = subprocess.run(
        (
            sys.executable,
            str(candidate_root / "experiments/internal_test_pair_v1/worker.py"),
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


def stratified_bootstrap(cases, predictions: dict[str, list[CasePrediction]]) -> dict:
    """Paired difference CI, 2 draws/stratum, seed 0, 20k resamples.

    Percentiles use zero-based p*(n-1) linear interpolation on sorted draws.
    This is a descriptive internal interval, not a population claim.
    """
    from evals.structured_nlu.ai_reviewed_internal_policy_v1 import _category

    strata: dict[tuple[str, str], list[int]] = {}
    for index, case in enumerate(cases):
        scope = "in" if _category(case) == "in_scope" else "out"
        strata.setdefault((case.scenario_key, scope), []).append(index)
    if len(strata) != 32 or any(len(indices) != 2 for indices in strata.values()):
        raise ValueError("bootstrap strata differ from 32×2 preregistration")
    deltas = []
    for case, before, after in zip(cases, predictions["baseline"], predictions["candidate"], strict=True):
        before_ok = score_predictions((case,), (before,)).counts.fully_correct_cases == 1
        after_ok = score_predictions((case,), (after,)).counts.fully_correct_cases == 1
        deltas.append(int(after_ok) - int(before_ok))
    rng = random.Random(0)
    draws = []
    ordered = [strata[key] for key in sorted(strata)]
    for _ in range(20_000):
        total = 0
        for first, second in ordered:
            total += deltas[first if rng.randrange(2) == 0 else second]
            total += deltas[first if rng.randrange(2) == 0 else second]
        draws.append(total / 64)
    draws.sort()

    def percentile(p: float) -> float:
        position = p * (len(draws) - 1)
        lower = int(position)
        fraction = position - lower
        return draws[lower] * (1 - fraction) + draws[min(lower + 1, len(draws) - 1)] * fraction

    return {
        "method": "paired_stratified_bootstrap_32x2_percentile_linear_v1",
        "resamples": 20_000,
        "seed": 0,
        "difference": sum(deltas) / 64,
        "ci95": [percentile(0.025), percentile(0.975)],
    }


def safety_counts(
    cases, predictions: dict[str, list[CasePrediction]], category_by_id: dict[str, str]
) -> dict:
    """Guard trigger counts; invalid output cannot count as a detected hazard."""
    counts = {
        category: {"denominator": 0, "baseline_guard": 0, "candidate_guard": 0}
        for category in gate.SAFETY_CATEGORIES
    }
    new_direct_misses = 0
    for case, before, after in zip(cases, predictions["baseline"], predictions["candidate"], strict=True):
        category = category_by_id[case.id]
        before_guard = bool(before.final_output and before.final_output.fields.get("safety_status") == "safety_issue")
        after_guard = bool(after.final_output and after.final_output.fields.get("safety_status") == "safety_issue")
        counts[category]["denominator"] += 1
        counts[category]["baseline_guard"] += int(before_guard)
        counts[category]["candidate_guard"] += int(after_guard)
        if category == "direct" and before_guard and not after_guard:
            new_direct_misses += 1
    if any(row["denominator"] != 4 for row in counts.values()):
        raise ValueError("safety16 category denominator differs")
    return {
        "categories": counts,
        "direct_new_misses": new_direct_misses,
        "direct_candidate_misses": 4 - counts["direct"]["candidate_guard"],
        "negative_baseline_false_alarms": sum(counts[key]["baseline_guard"] for key in ("other_source", "nonoccurring")),
        "negative_candidate_false_alarms": sum(counts[key]["candidate_guard"] for key in ("other_source", "nonoccurring")),
        "negative_denominator": 8,
        "gate_status": "no_new_direct_miss" if new_direct_misses == 0 else "failed_new_direct_miss",
    }


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
    if protocol["kind"] == gate.KIND:
        dataset_key, dataset_relative, case_count, result_kind, result_scope = (
            "test_dataset", gate.INPUT_PATHS["test_dataset"], 64, RESULT_KIND, gate.SCOPE
        )
    elif protocol["kind"] == gate.SAFETY_KIND:
        dataset_key, dataset_relative, case_count, result_kind, result_scope = (
            "safety_dataset", gate.SAFETY_INPUT_PATHS["safety_dataset"], 16,
            "ai_reviewed_internal_safety16_pair_v1_result", gate.SAFETY_SCOPE
        )
    else:
        raise ValueError("unknown paired suite")
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
        result["kind"] != result_kind
        or result["scope"] != result_scope
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
        (candidate_root / dataset_relative).read_bytes()
    )
    by_id = {case.id: case for case in case_data.cases}
    if set(by_id) != set(protocol["case_order"]):
        raise ValueError("test case set differs")
    cases = tuple(by_id[case_id] for case_id in protocol["case_order"])
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
                dataset_key=dataset_key,
                dataset_relative=dataset_relative,
            )
            if _semantic_prediction(prediction) != _semantic_prediction(replay):
                raise ValueError("recorded prediction differs from raw replay")
            predictions[arm].append(prediction)
            count += 1
            if count % gate.LOCAL_RUNTIME["restart_interval_arm_evaluations"] == 0 and count < 2 * case_count:
                previous = _boundary(
                    take(), phase="before_restart", completed=count, previous=previous
                )
                previous = _boundary(
                    take(), phase="after_restart", completed=count, previous=previous
                )
    previous = _boundary(take(), phase="final", completed=2 * case_count, previous=previous)
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
        "kind": result_kind,
        "scope": result_scope,
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
        "kind": "ai_reviewed_internal_test_pair_v1_verified_receipt" if case_count == 64 else "ai_reviewed_internal_safety16_pair_v1_verified_receipt",
        "verification_status": "verified",
        "publication_status": "provisional_pending_fresh_safety16_and_exposure_audit" if case_count == 64 else "safety16_raw_verified_exposure_audit_pending",
        "scope": result_scope,
        "cases": case_count,
        "arm_evaluations": 2 * case_count,
        "protocol_sha256": protocol_sha,
        "journal_sha256": result["journal_sha256"],
        "unverified_result_sha256": gate._file_sha(output),
        "summaries": summaries,
        "paired_counts": paired,
    }
    if case_count == 64:
        verified["safety_condition"] = "unverified"
        verified["bootstrap"] = stratified_bootstrap(cases, predictions)
    else:
        category_data = gate._strict_json((candidate_root / gate.SAFETY_INPUT_PATHS["safety_category_ledger"]).read_bytes())
        verified["safety_counts"] = safety_counts(
            cases, predictions,
            {row["case_id"]: row["category"] for row in category_data["categories"]},
        )
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
