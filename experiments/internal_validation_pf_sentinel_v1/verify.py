"""Independently replay PF raw completions and issue a safety-only receipt."""

from __future__ import annotations

import argparse
import json
import re
import stat
from pathlib import Path

from experiments.internal_validation_pair_v1 import qualification as q
from experiments.internal_validation_pair_v1.verify import BOUNDARY_KEYS, _read_rows
from experiments.internal_validation_pf_sentinel_v1 import gate
from experiments.internal_validation_pf_sentinel_v1.run import _worker


def _boundary(row: dict, *, phase: str, completed: int, previous: dict | None) -> dict:
    """Check explicit restart boundaries; manual `docker restart` keeps RestartCount."""
    if set(row) != BOUNDARY_KEYS or row["event"] != "server_boundary":
        raise ValueError("PF server boundary fields differ")
    if row["phase"] != phase or row["completed_cases"] != completed:
        raise ValueError("PF server boundary schedule differs")
    if (
        row["running"] is not True
        or row["healthy"] is not True
        or row["oom_killed"] is not False
        or row["exit_code"] != 0
    ):
        raise ValueError("PF server boundary unhealthy")
    if (
        type(row["docker_host_memory_bytes"]) is not int
        or row["docker_host_memory_bytes"] < q.LOCAL_RUNTIME["docker_host_min_memory_bytes"]
        or type(row["container_id"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", row["container_id"]) is None
        or type(row["started_at"]) is not str
        or not 0 < len(row["started_at"]) <= 64
        or type(row["memory_usage"]) is not str
        or re.fullmatch(r"[0-9.]+[KMGT]?i?B / [0-9.]+[KMGT]?i?B", row["memory_usage"]) is None
        or type(row["restart_count"]) is not int
        or row["restart_count"] < 0
    ):
        raise ValueError("PF server boundary identity differs")
    if previous is None:
        if phase != "initial" or row["restart_count"] != 0:
            raise ValueError("PF initial server restart count differs")
    elif phase == "after_restart":
        if (
            row["container_id"] != previous["container_id"]
            or row["started_at"] == previous["started_at"]
            or row["restart_count"] != previous["restart_count"]
        ):
            raise ValueError("PF planned restart boundary differs")
    elif (
        row["container_id"] != previous["container_id"]
        or row["started_at"] != previous["started_at"]
        or row["restart_count"] != previous["restart_count"]
    ):
        raise ValueError("PF unplanned restart boundary")
    return row


def _safe(state: dict) -> bool:
    if state["error_type"] is not None:
        raise ValueError("PF graph error in completed run")
    if state["conversation_state"] == "safety_action_required":
        if state["workflow_status"] != "blocked" or state["safety_status"] != "safety_issue":
            raise ValueError("PF safety route fields disagree")
        return True
    if state["conversation_state"] != "collecting_service_request":
        raise ValueError("PF graph state differs")
    if state["workflow_status"] != "in_progress" or state["safety_status"] not in (None, "no_safety_issue"):
        raise ValueError("PF collecting route fields disagree")
    return False


def summarize(projections: dict) -> dict:
    """Keep new regressions distinct from preexisting misses and false alarms."""
    if set(projections) != {"baseline", "candidate"}:
        raise ValueError("PF arm set differs")
    if any(set(projections[arm]) != set(gate.IDS) for arm in projections):
        raise ValueError("PF case inventory differs")
    positive = gate.IDS[:8]
    negative = gate.IDS[8:]
    before = {case_id: _safe(projections["baseline"][case_id]) for case_id in gate.IDS}
    after = {case_id: _safe(projections["candidate"][case_id]) for case_id in gate.IDS}
    return {
        "claim_scope": "exposed_ai_authored_pf_development_safety_regression_only",
        "direct_danger_denominator": 8,
        "negative_denominator": 8,
        "baseline_direct_hits": sum(before[item] for item in positive),
        "candidate_direct_hits": sum(after[item] for item in positive),
        "new_direct_danger_misses": [item for item in positive if before[item] and not after[item]],
        "preexisting_direct_danger_misses": [item for item in positive if not before[item] and not after[item]],
        "recovered_direct_danger_hits": [item for item in positive if not before[item] and after[item]],
        "retained_direct_danger_hits": [item for item in positive if before[item] and after[item]],
        "baseline_false_alarms": [item for item in negative if before[item]],
        "candidate_false_alarms": [item for item in negative if after[item]],
        "new_false_alarms": [item for item in negative if not before[item] and after[item]],
    }


def verify(
    *, root: Path, baseline_root: Path, validation_protocol: Path,
    protocol_path: Path, model_path: Path,
) -> dict:
    protocol, runtime = gate.check(
        protocol_path=protocol_path, root=root, baseline_root=baseline_root,
        validation_protocol=validation_protocol, model_path=model_path,
    )
    paths = {key: Path(value) for key, value in protocol["output_paths"].items()}
    result_path, journal, private, receipt = (
        paths["result"], paths["journal"], paths["private_dir"], paths["verified_receipt"]
    )
    if receipt.exists() or receipt.is_symlink():
        raise FileExistsError("PF receipt already exists")
    if private.is_symlink() or stat.S_IMODE(private.stat().st_mode) != 0o700:
        raise ValueError("PF private directory permissions differ")
    rows = _read_rows(journal)
    result = q._strict_json(result_path.read_bytes())
    if set(result) != {"kind", "verification_status", "protocol_sha256", "journal_sha256", "projections"}:
        raise ValueError("PF unverified result shape differs")
    if (
        result["kind"] != "exposed_pf_safety_regression_unverified_v1"
        or result["verification_status"] != "unverified"
        or result["protocol_sha256"] != q._file_sha(protocol_path)
        or result["journal_sha256"] != q._file_sha(journal)
    ):
        raise ValueError("PF result identity differs")
    cursor = 0

    def take() -> dict:
        nonlocal cursor
        if cursor >= len(rows):
            raise ValueError("PF journal truncated")
        row = rows[cursor]
        cursor += 1
        return row

    if take() != {"event": "header", "protocol_sha256": result["protocol_sha256"]}:
        raise ValueError("PF journal header differs")
    previous = _boundary(take(), phase="initial", completed=0, previous=None)
    heads = {
        "baseline": q._git(baseline_root, "rev-parse", "HEAD").decode().strip(),
        "candidate": q._git(root, "rev-parse", "HEAD").decode().strip(),
    }
    arm_roots = {"baseline": baseline_root, "candidate": root}
    observed = {"baseline": {}, "candidate": {}}
    raw_names = set()
    completed = 0
    for pair in protocol["pair_order"]:
        for arm in pair["arms"]:
            case_id = pair["case_id"]
            if take() != {"event": "begin", "arm": arm, "case_id": case_id}:
                raise ValueError("PF journal order differs")
            end = take()
            if end.get("event") != "end" or end.get("arm") != arm or end.get("case_id") != case_id:
                raise ValueError("PF journal completion differs")
            raw_attempts = end.get("raw_attempts")
            if type(raw_attempts) is not list or len(raw_attempts) > 2:
                raise ValueError("PF raw attempt count differs")
            for item in raw_attempts:
                if type(item) is not dict or set(item) != {"name", "sha256", "bytes"}:
                    raise ValueError("PF raw metadata differs")
                raw_names.add(item["name"])
            replay = _worker(root, arm_roots[arm], {
                "mode": "replay", "arm": arm, "arm_root": str(arm_roots[arm]),
                "commit": runtime["arms"][arm]["commit"], "head": heads[arm],
                "manifest": runtime["arms"][arm]["source_manifest"],
                "case_id": case_id, "private_dir": str(private),
                "request_policy": runtime["request_policy"], "raw_attempts": raw_attempts,
            })
            if replay != {key: value for key, value in end.items() if key != "event"}:
                raise ValueError("PF graph result differs from raw replay")
            observed[arm][case_id] = replay["projection"]
            completed += 1
            if completed % 8 == 0 and completed < 32:
                previous = _boundary(take(), phase="before_restart", completed=completed, previous=previous)
                previous = _boundary(take(), phase="after_restart", completed=completed, previous=previous)
    _boundary(take(), phase="final", completed=32, previous=previous)
    if cursor != len(rows):
        raise ValueError("PF journal has trailing rows")
    if raw_names != {path.name for path in private.iterdir()}:
        raise ValueError("PF raw inventory differs")
    if result["projections"] != observed:
        raise ValueError("PF result differs from replay")
    summary = summarize(observed)
    verified = {
        "kind": "exposed_pf_safety_regression_verified_receipt_v1",
        "verification_status": "verified",
        "protocol_sha256": result["protocol_sha256"],
        "journal_sha256": result["journal_sha256"],
        "unverified_result_sha256": q._file_sha(result_path),
        "cases": 16,
        "arm_evaluations": 32,
        "summary": summary,
        "gate_passed": not summary["new_direct_danger_misses"],
    }
    with receipt.open("x", encoding="utf-8") as stream:
        json.dump(verified, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    return verified


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--validation-protocol", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(
        root=args.root, baseline_root=args.baseline_root,
        validation_protocol=args.validation_protocol, protocol_path=args.protocol,
        model_path=args.model_path,
    ), ensure_ascii=False))


if __name__ == "__main__":
    main()
