"""Run 16 exposed PF safety pairs on the frozen Q5 service; withhold scores."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from experiments.internal_validation_pair_v1 import qualification as q
from experiments.internal_validation_pf_sentinel_v1 import gate
from experiments.nlu_current_baseline_v1 import run as server


def _worker(root: Path, arm_root: Path, payload: dict) -> dict:
    result = subprocess.run(
        (sys.executable, str(root / gate.HARNESS / "worker.py")),
        cwd=arm_root, input=json.dumps(payload, ensure_ascii=False), text=True,
        capture_output=True, timeout=600,
    )
    if result.returncode:
        raise ValueError(f"PF worker failed: {payload['arm']}/{payload['case_id']}")
    row = q._strict_json(result.stdout.encode())
    if row.get("arm") != payload["arm"] or row.get("case_id") != payload["case_id"]:
        raise ValueError("PF worker identity differs")
    return row


def _boundary(stream, name: str, model_path: Path, runtime: dict, phase: str, count: int) -> dict:
    return server._server_boundary(
        stream, name, model_path, runtime, phase=phase, completed_cases=count
    )


def run(
    *, root: Path, baseline_root: Path, validation_protocol: Path,
    protocol_path: Path, model_path: Path, container_name: str,
) -> dict:
    protocol, runtime = gate.check(
        protocol_path=protocol_path, root=root, baseline_root=baseline_root,
        validation_protocol=validation_protocol, model_path=model_path,
    )
    paths = {key: Path(value) for key, value in protocol["output_paths"].items()}
    if any(path.exists() or path.is_symlink() for path in paths.values()):
        raise FileExistsError("PF output already exists; do not resume or overwrite")
    result_path, journal = paths["result"], paths["journal"]
    private = paths["private_dir"]
    if not all(path.parent.is_dir() for path in paths.values()):
        raise ValueError("PF output parent directory missing")
    observed = server.verify_container(container_name, model_path, runtime["local_runtime"])
    old_umask = os.umask(0o077)
    try:
        private.mkdir(mode=0o700)
    finally:
        os.umask(old_umask)
    if stat.S_IMODE(private.stat().st_mode) != 0o700:
        raise ValueError("PF private directory permissions differ")
    heads = {
        "baseline": q._git(baseline_root, "rev-parse", "HEAD").decode().strip(),
        "candidate": q._git(root, "rev-parse", "HEAD").decode().strip(),
    }
    arm_roots = {"baseline": baseline_root, "candidate": root}
    projections = {"baseline": {}, "candidate": {}}
    with journal.open("x", encoding="utf-8") as stream:
        server._append(stream, {"event": "header", "protocol_sha256": q._file_sha(protocol_path)})
        first = _boundary(stream, container_name, model_path, runtime, "initial", 0)
        if server._identity(first) != server._identity(observed) or first["restart_count"] != 0:
            raise ValueError("PF initial server identity differs")
        identity = server._identity(first)
        restart_count = 0
        completed = 0
        for pair in protocol["pair_order"]:
            for arm in pair["arms"]:
                current = server.verify_container(container_name, model_path, runtime["local_runtime"])
                if server._identity(current) != identity or current["RestartCount"] != restart_count:
                    raise ValueError("PF unplanned server restart")
                case_id = pair["case_id"]
                server._append(stream, {"event": "begin", "arm": arm, "case_id": case_id})
                row = _worker(root, arm_roots[arm], {
                    "mode": "live", "arm": arm, "arm_root": str(arm_roots[arm]),
                    "commit": runtime["arms"][arm]["commit"], "head": heads[arm],
                    "manifest": runtime["arms"][arm]["source_manifest"],
                    "case_id": case_id, "private_dir": str(private),
                    "request_policy": runtime["request_policy"], "raw_attempts": [],
                })
                server._append(stream, {"event": "end", **row})
                state = row["projection"]
                if state["error_type"] is not None:
                    raise ValueError("PF graph error; entire gate invalid")
                projections[arm][case_id] = state
                completed += 1
                if completed % 8 == 0 and completed < 32:
                    before = _boundary(stream, container_name, model_path, runtime, "before_restart", completed)
                    if server._identity(before) != identity or before["restart_count"] != restart_count:
                        raise ValueError("PF server changed before planned restart")
                    subprocess.run(
                        ("docker", "restart", "--time", "10", container_name),
                        check=True, capture_output=True, timeout=150,
                    )
                    after = _boundary(stream, container_name, model_path, runtime, "after_restart", completed)
                    if (
                        before["container_id"] != after["container_id"]
                        or before["started_at"] == after["started_at"]
                        or after["restart_count"] != restart_count
                    ):
                        raise ValueError("PF planned restart identity differs")
                    identity = server._identity(after)
        final = _boundary(stream, container_name, model_path, runtime, "final", 32)
        if server._identity(final) != identity or final["restart_count"] != restart_count:
            raise ValueError("PF final server identity differs")
    result = {
        "kind": "exposed_pf_safety_regression_unverified_v1",
        "verification_status": "unverified",
        "protocol_sha256": q._file_sha(protocol_path),
        "journal_sha256": q._file_sha(journal),
        "projections": projections,
    }
    with result_path.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--validation-protocol", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--container-name", required=True)
    args = parser.parse_args()
    run(
        root=args.root, baseline_root=args.baseline_root,
        validation_protocol=args.validation_protocol, protocol_path=args.protocol,
        model_path=args.model_path, container_name=args.container_name,
    )


if __name__ == "__main__":
    main()
