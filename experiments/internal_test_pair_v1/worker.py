"""One frozen-arm live or offline NLU case; never aggregate a score here."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import urllib.error
from pathlib import Path

COMPLETION_ERRORS = (
    urllib.error.URLError,
    TimeoutError,
    OSError,
    ValueError,
    TypeError,
    KeyError,
    IndexError,
)


class CompletionFailure(RuntimeError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(name)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_arm(
    root: Path, commit: str, manifest: dict[str, str], *, arm: str, expected_head: str
) -> None:
    head = subprocess.run(
        ("git", "rev-parse", "HEAD"), cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = subprocess.run(
        ("git", "status", "--porcelain"), cwd=root, check=True, capture_output=True
    ).stdout
    if dirty:
        raise ValueError("arm worktree is not frozen and clean")
    if head != expected_head:
        raise ValueError("arm worktree HEAD changed during paired run")
    if arm == "baseline" and head != commit:
        raise ValueError("baseline worktree HEAD differs")
    if arm == "candidate":
        subprocess.run(
            ("git", "merge-base", "--is-ancestor", commit, head),
            cwd=root,
            check=True,
            capture_output=True,
            timeout=30,
        )
    for relative, expected in manifest.items():
        source = root / relative
        if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
            raise ValueError("arm source path escapes worktree")
        if _file_sha(source) != expected:
            raise ValueError(f"arm source differs: {relative}")


def _private_dir(path: Path) -> None:
    if path.is_symlink() or not path.is_dir() or stat.S_IMODE(path.stat().st_mode) != 0o700:
        raise ValueError("private raw directory boundary differs")


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
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError("private raw response mode differs")
    return {"raw_sha256": _sha(encoded), "raw_bytes": len(encoded)}


def one_case(
    *,
    mode: str,
    arm_root: Path,
    arm: str,
    case_id: str,
    private_dir: Path,
    request: dict,
    commit: str,
    manifest: dict[str, str],
    expected_head: str,
    data_root: Path,
    data_commit: str,
    dataset_sha256: str,
    dataset_relative: str = "evals/structured_nlu/data/ai_heldout/ai-internal-test-v1-reviewed.json",
    recorded_attempts: list[dict] | None = None,
) -> dict:
    """Run the arm's own analyzer after checking its committed source bytes."""
    _check_arm(arm_root, commit, manifest, arm=arm, expected_head=expected_head)
    _private_dir(private_dir)
    if arm not in {"baseline", "candidate"} or mode not in {"live", "replay"}:
        raise ValueError("arm or worker mode differs")
    sys.path.insert(0, str(arm_root.resolve()))
    from evals.structured_nlu.ai_heldout import AIHeldoutDataset
    from scripts.run_ai_heldout_pair import _post_completion, _run_case

    if dataset_relative not in {
        "evals/structured_nlu/data/ai_heldout/ai-internal-test-v1-reviewed.json",
        "evals/structured_nlu/data/ai_heldout/ai-internal-safety16-v1-reviewed.json",
    }:
        raise ValueError("dataset path is outside the preregistered suites")
    relative = dataset_relative
    dataset_bytes = (data_root / relative).read_bytes()
    if _sha(dataset_bytes) != dataset_sha256:
        raise ValueError("common TEST dataset digest differs")
    frozen = subprocess.run(
        ("git", "show", f"{data_commit}:{relative}"),
        cwd=data_root,
        check=True,
        capture_output=True,
        timeout=30,
    ).stdout
    if frozen != dataset_bytes:
        raise ValueError("common TEST dataset differs from input commit")
    dataset = AIHeldoutDataset.model_validate_json(dataset_bytes)
    matches = [case for case in dataset.cases if case.id == case_id]
    if len(matches) != 1:
        raise ValueError("test case ID differs")
    case = matches[0]
    from types import SimpleNamespace

    policy = SimpleNamespace(**request)
    attempts: list[dict] = []

    def completion(endpoint, model_id, messages, request_policy):
        ordinal = len(attempts) + 1
        if ordinal > 2:
            raise ValueError("completion retry limit differs")
        path = private_dir / f"{arm}-{case_id}-attempt{ordinal}.txt"
        if mode == "replay":
            if recorded_attempts is None or ordinal > len(recorded_attempts):
                raise RuntimeError("replay requested an unrecorded completion")
            item = recorded_attempts[ordinal - 1]
            if item.get("attempt") != ordinal or item.get("status") != "received":
                raise RuntimeError("replay metadata differs")
            if (
                path.is_symlink()
                or not path.is_file()
                or stat.S_IMODE(path.stat().st_mode) != 0o600
            ):
                raise RuntimeError("replay private raw file differs")
            raw_bytes = path.read_bytes()
            if len(raw_bytes) != item.get("raw_bytes") or _sha(raw_bytes) != item.get("raw_sha256"):
                raise RuntimeError("replay private raw digest differs")
            raw = raw_bytes.decode("utf-8")
            attempts.append(item)
            return raw
        try:
            raw = _post_completion(endpoint, model_id, messages, request_policy)
        except COMPLETION_ERRORS as error:
            name = type(error).__name__
            attempts.append(
                {
                    "attempt": ordinal,
                    "status": "transport_error",
                    "raw_sha256": None,
                    "raw_bytes": None,
                    "error_type": name,
                }
            )
            raise CompletionFailure(name) from None
        metadata = _save(path, raw)
        attempts.append({"attempt": ordinal, "status": "received", **metadata, "error_type": None})
        return raw

    try:
        prediction = _run_case(
            case,
            endpoint=request["endpoint"],
            model_id=request["model_id"],
            policy=policy,
            completion_post=completion,
        )
    except CompletionFailure as error:
        return {
            "status": "completion_error",
            "case_id": case_id,
            "arm": arm,
            "error_type": error.name,
            "raw_attempts": attempts,
        }
    if len(attempts) != len(prediction.attempts):
        raise ValueError("raw attempt count differs")
    if mode == "replay" and len(attempts) != len(recorded_attempts or []):
        raise ValueError("replay unused raw attempt differs")
    return {
        "status": "complete",
        "case_id": case_id,
        "arm": arm,
        "prediction": prediction.model_dump(mode="json"),
        "raw_attempts": attempts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("live", "replay"), required=True)
    parser.add_argument("--arm-root", type=Path, required=True)
    parser.add_argument("--arm", choices=("baseline", "candidate"), required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    args = parser.parse_args()
    data = json.load(sys.stdin)
    result = one_case(
        mode=args.mode,
        arm_root=args.arm_root,
        arm=args.arm,
        case_id=args.case_id,
        private_dir=args.private_dir,
        request=data["request_policy"],
        commit=data["commit"],
        manifest=data["source_manifest"],
        expected_head=data["worktree_head"],
        data_root=Path(data["data_root"]),
        data_commit=data["data_commit"],
        dataset_sha256=data["dataset_sha256"],
        dataset_relative=data.get(
            "dataset_relative",
            "evals/structured_nlu/data/ai_heldout/ai-internal-test-v1-reviewed.json",
        ),
        recorded_attempts=data.get("raw_attempts"),
    )
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    if result["status"] != "complete":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
