"""Freeze and run the current live NLU path on the exposed AH development set.

This is an error-analysis baseline. It is not the human-authored official test,
and the already exposed AH cases cannot become a new independent test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import urllib.error
from pathlib import Path
from types import SimpleNamespace

from evals.structured_nlu.ai_heldout import load_reviewed_ai_heldout
from evals.structured_nlu.metrics import score_predictions
from experiments.as_safety_v4 import run as v4
from scripts.run_ai_heldout_pair import PROMPT_SOURCES, _post_completion, _run_case

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
INPUTS = {
    "dataset": DATA / "ai-heldout-reviewed.v1.json",
    "review_ledger": DATA / "ai-heldout-review-ledger.v1.json",
}
KIND = "nlu_current_baseline_v1_development"
RESULT_KIND = "nlu_current_baseline_v1_result"
SCOPE = "exposed_ai_authored_user_adjudicated_development_only"
MODEL_SHA = v4.MODEL_SHA
IMAGE = v4.IMAGE
RUNTIME = v4.RUNTIME
REQUEST = {
    "max_tokens": 180,
    "temperature": 0,
    "repeat_penalty": 1.05,
    "stop": ["<|eot_id|>"],
    "timeout_seconds": 180,
    "retry_policy": "one_retry_after_contract_failure",
    "cache_policy": "mixed",
    "endpoint": "http://127.0.0.1:18081/v1/chat/completions",
    "model_id": "kanana-q5",
}
SOURCE_PATHS = tuple(
    sorted(
        set(PROMPT_SOURCES)
        | {
            "scripts/run_ai_heldout_pair.py",
            "experiments/as_safety_v4/run.py",
            "experiments/nlu_current_baseline_v1/run.py",
            "experiments/nlu_current_baseline_v1/verify.py",
        }
    )
)
PROTOCOL_KEYS = {
    "kind",
    "scope",
    "frozen_code_commit",
    "input_hashes",
    "source_manifest",
    "model_sha256",
    "server_image_digest",
    "request_policy",
    "local_runtime",
    "case_order",
}
COMPLETION_ERRORS = (
    urllib.error.URLError,
    TimeoutError,
    OSError,
    ValueError,
    TypeError,
    KeyError,
    IndexError,
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=ROOT, check=True, capture_output=True).stdout


def _reviewed():
    reviewed = load_reviewed_ai_heldout(INPUTS["dataset"], INPUTS["review_ledger"])
    cases = reviewed.dataset.cases
    if len(cases) != 32 or tuple(case.id for case in cases) != tuple(
        f"ai-heldout-ah{i:02}" for i in range(1, 33)
    ):
        raise ValueError("AH development case order differs")
    if set(reviewed.scenario_counts.values()) != {2} or len(reviewed.scenario_counts) != 16:
        raise ValueError("AH development scenario balance differs")
    return reviewed


def build_protocol(commit: str, model_path: Path) -> dict:
    """Bind every input and prompt/scorer source to one pre-call Git commit."""
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("full frozen code commit required")
    if _file_sha(model_path) != MODEL_SHA:
        raise ValueError("Q5 model file differs")
    reviewed = _reviewed()
    inputs = {}
    for key, path in INPUTS.items():
        relative = path.relative_to(ROOT).as_posix()
        frozen = _git("show", f"{commit}:{relative}")
        if path.read_bytes() != frozen:
            raise ValueError(f"input differs from frozen commit: {key}")
        inputs[key] = _sha(frozen)
    sources = {}
    for relative in SOURCE_PATHS:
        frozen = _git("show", f"{commit}:{relative}")
        if (ROOT / relative).read_bytes() != frozen:
            raise ValueError(f"source differs from frozen commit: {relative}")
        sources[relative] = _sha(frozen)
    return {
        "kind": KIND,
        "scope": SCOPE,
        "frozen_code_commit": commit,
        "input_hashes": inputs,
        "source_manifest": sources,
        "model_sha256": MODEL_SHA,
        "server_image_digest": IMAGE,
        "request_policy": REQUEST,
        "local_runtime": RUNTIME,
        "case_order": [case.id for case in reviewed.dataset.cases],
    }


def load_protocol(path: Path, model_path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    protocol = json.loads(raw)
    if type(protocol) is not dict or set(protocol) != PROTOCOL_KEYS:
        raise ValueError("protocol fields differ")
    if protocol != build_protocol(protocol["frozen_code_commit"], model_path):
        raise ValueError("protocol differs from frozen inputs or code")
    try:
        relative = path.resolve().relative_to(ROOT).as_posix()
    except ValueError as error:
        raise ValueError("protocol must be in repository") from error
    if _git("show", f"HEAD:{relative}") != raw:
        raise ValueError("protocol must be committed before model calls")
    if _git("status", "--porcelain").strip():
        raise ValueError("checkout differs before model calls")
    return protocol, _sha(raw)


def _append(stream, row: dict) -> None:
    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def _private_output_dir(path: Path) -> None:
    if path.resolve().is_relative_to(ROOT) or path.exists() or path.is_symlink():
        raise ValueError("private raw directory must be new and outside repository")
    path.mkdir(mode=0o700, parents=False)
    path.chmod(0o700)
    if stat.S_IMODE(path.stat().st_mode) != 0o700:
        raise ValueError("private raw directory mode differs")


def _save_raw(path: Path, raw: str) -> tuple[str, int]:
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
    return _sha(encoded), len(encoded)


def run(
    *,
    protocol_path: Path,
    model_path: Path,
    output: Path,
    journal: Path,
    private_dir: Path,
    container_name: str,
) -> dict:
    """Preserve every attempt and refuse replay of an interrupted journal."""
    if output.resolve() == journal.resolve():
        raise ValueError("result and journal paths must differ")
    if output.exists() or journal.exists() or private_dir.exists() or private_dir.is_symlink():
        raise FileExistsError("existing result, journal or private raw requires manual audit")
    if private_dir.resolve().is_relative_to(ROOT):
        raise ValueError("private raw directory must be outside repository")
    protocol, protocol_sha = load_protocol(protocol_path, model_path)
    v4.verify_container(container_name, model_path)
    cases = _reviewed().dataset.cases
    policy = SimpleNamespace(**protocol["request_policy"])
    predictions = []
    _private_output_dir(private_dir)
    with journal.open("x", encoding="utf-8") as stream:
        _append(stream, {"event": "header", "protocol_sha256": protocol_sha})
        for case in cases:
            _append(stream, {"event": "begin", "case_id": case.id})
            raw_attempts = []

            def completion_post(
                endpoint,
                model_id,
                messages,
                request_policy,
                *,
                _case_id=case.id,
                _raw_attempts=raw_attempts,
            ):
                attempt = len(_raw_attempts) + 1
                if attempt > 2:
                    raise ValueError("live retry count exceeds protocol")
                try:
                    raw = _post_completion(endpoint, model_id, messages, request_policy)
                except COMPLETION_ERRORS as error:
                    error_type = type(error).__name__
                    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", error_type) is None:
                        raise ValueError("completion error type outside bounded status") from error
                    _raw_attempts.append(
                        {
                            "attempt": attempt,
                            "status": "transport_error",
                            "raw_sha256": None,
                            "raw_bytes": None,
                            "error_type": error_type,
                        }
                    )
                    raise
                sha, size = _save_raw(private_dir / f"{_case_id}-attempt{attempt}.txt", raw)
                _raw_attempts.append(
                    {
                        "attempt": attempt,
                        "status": "received",
                        "raw_sha256": sha,
                        "raw_bytes": size,
                        "error_type": None,
                    }
                )
                return raw

            prediction = _run_case(
                case,
                endpoint=policy.endpoint,
                model_id=policy.model_id,
                policy=policy,
                completion_post=completion_post,
            )
            if len(raw_attempts) != len(prediction.attempts):
                raise ValueError("raw attempt count differs from live validator")
            _append(
                stream,
                {
                    "event": "end",
                    "case_id": case.id,
                    "prediction": prediction.model_dump(mode="json"),
                    "raw_attempts": raw_attempts,
                },
            )
            predictions.append(prediction)
        if tuple(prediction.case_id for prediction in predictions) != tuple(protocol["case_order"]):
            raise ValueError("prediction case order differs")
        summary = score_predictions(cases, tuple(predictions)).to_dict()
        _append(stream, {"event": "summary", "summary": summary})
    result = {
        "kind": RESULT_KIND,
        "protocol_sha256": protocol_sha,
        "journal_sha256": _file_sha(journal),
        "predictions": [prediction.model_dump(mode="json") for prediction in predictions],
        "summary": summary,
    }
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build-protocol")
    build.add_argument("--model-path", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)
    execute = sub.add_parser("run")
    execute.add_argument("--protocol", required=True, type=Path)
    execute.add_argument("--model-path", required=True, type=Path)
    execute.add_argument("--output", required=True, type=Path)
    execute.add_argument("--journal", required=True, type=Path)
    execute.add_argument("--private-dir", required=True, type=Path)
    execute.add_argument("--container-name", required=True)
    args = parser.parse_args()
    if args.command == "build-protocol":
        if _git("status", "--porcelain").strip():
            raise ValueError("checkout must be clean before protocol build")
        commit = _git("rev-parse", "HEAD").decode().strip()
        protocol = build_protocol(commit, args.model_path)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(protocol, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
    else:
        run(
            protocol_path=args.protocol,
            model_path=args.model_path,
            output=args.output,
            journal=args.journal,
            private_dir=args.private_dir,
            container_name=args.container_name,
        )


if __name__ == "__main__":
    main()
