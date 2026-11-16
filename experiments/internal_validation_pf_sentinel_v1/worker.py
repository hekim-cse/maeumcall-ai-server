"""Run or replay one PF graph case under one frozen service revision."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _frozen_arm(root: Path, commit: str, head: str, manifest: dict[str, str]) -> None:
    observed = subprocess.run(
        ("git", "rev-parse", "HEAD"), cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    if observed != head:
        raise ValueError("PF arm HEAD changed")
    if subprocess.run(
        ("git", "status", "--porcelain"), cwd=root, check=True, capture_output=True
    ).stdout:
        raise ValueError("PF arm worktree is dirty")
    subprocess.run(
        ("git", "merge-base", "--is-ancestor", commit, head),
        cwd=root, check=True, capture_output=True,
    )
    for name, digest in manifest.items():
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("PF arm source escapes worktree")
        if _sha(path.read_bytes()) != digest:
            raise ValueError(f"PF arm source differs: {name}")


def _raw_path(private: Path, arm: str, case_id: str, index: int) -> Path:
    if arm not in {"baseline", "candidate"} or not case_id.startswith("nlu-safety-postfreeze-pf"):
        raise ValueError("PF raw identity differs")
    return private / f"{arm}-{case_id}-{index:02}.raw"


def _save(path: Path, raw: str) -> dict:
    encoded = raw.encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return {"name": path.name, "sha256": _sha(encoded), "bytes": len(encoded)}


def _read(path: Path, record: dict) -> str:
    if set(record) != {"name", "sha256", "bytes"} or record["name"] != path.name:
        raise ValueError("PF raw record differs")
    if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError("PF raw file permissions differ")
    encoded = path.read_bytes()
    if len(encoded) != record["bytes"] or _sha(encoded) != record["sha256"]:
        raise ValueError("PF raw response differs")
    return encoded.decode("utf-8")


def _projection(result: dict) -> dict:
    projected = json.loads(json.dumps(result, ensure_ascii=False))
    for attempt in projected["attempts"]:
        attempt.pop("latency_ms")
    return projected


def one_case(payload: dict) -> dict:
    """Use recorded completions for replay; never call HTTP in replay mode."""
    if set(payload) != {
        "mode", "arm", "arm_root", "commit", "head", "manifest", "case_id",
        "private_dir", "request_policy", "raw_attempts",
    }:
        raise ValueError("PF worker payload shape differs")
    mode = payload["mode"]
    if mode not in {"live", "replay"}:
        raise ValueError("PF worker mode differs")
    root = Path(payload["arm_root"]).resolve()
    arm = payload["arm"]
    case_id = payload["case_id"]
    private = Path(payload["private_dir"])
    if private.is_symlink() or stat.S_IMODE(private.stat().st_mode) != 0o700:
        raise ValueError("PF private directory permissions differ")
    private = private.resolve()
    _frozen_arm(root, payload["commit"], payload["head"], payload["manifest"])
    sys.path.insert(0, str(root))
    from evals.structured_nlu.ai_heldout import AIHeldoutDataset
    from scripts.probe_nlu_safety_graph import run_graph_case
    from scripts.run_ai_heldout_pair import _post_completion

    dataset = AIHeldoutDataset.model_validate_json(
        (root / "evals/structured_nlu/data/ai_heldout/nlu-safety-postfreeze-reviewed.v1.json").read_bytes()
    )
    case = next((item for item in dataset.cases if item.id == case_id), None)
    if case is None:
        raise ValueError("PF case ID missing")
    records = []
    supplied = payload["raw_attempts"]
    if mode == "live" and supplied:
        raise ValueError("live worker must not receive raw attempts")

    def completion_post(endpoint, model_id, messages, policy):
        index = len(records)
        path = _raw_path(private, arm, case_id, index)
        if mode == "live":
            raw = _post_completion(endpoint, model_id, messages, policy)
            records.append(_save(path, raw))
            return raw
        if index >= len(supplied):
            raise ValueError("PF replay attempted extra model call")
        raw = _read(path, supplied[index])
        records.append(supplied[index])
        return raw

    request = payload["request_policy"]
    policy = SimpleNamespace(**request)
    result = run_graph_case(
        case, endpoint=request["endpoint"], model_id=request["model_id"],
        policy=policy, completion_post=completion_post,
    )
    if mode == "replay" and len(records) != len(supplied):
        raise ValueError("PF replay left unused raw attempts")
    if result["model_request_count"] != len(records):
        raise ValueError("PF graph call count differs")
    return {"arm": arm, "case_id": case_id, "projection": _projection(result), "raw_attempts": records}


def main() -> None:
    print(json.dumps(one_case(json.load(sys.stdin)), ensure_ascii=False))


if __name__ == "__main__":
    main()
