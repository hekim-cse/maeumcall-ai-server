"""Fail-closed preflight for AI-authored, user-adjudicated validation pairs.

This module cannot call a model or publish a score. It freezes inputs and both
code revisions before a separate runner may make its first completion request.
The known-corpus check is exact-text only; it is not a complete exposure audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import unicodedata
from pathlib import Path

from evals.structured_nlu.ai_reviewed_internal_policy_v1 import (
    _balanced_scenarios,
    _checked_split,
    policy_sha256,
)
from evals.structured_nlu.schema import DatasetSplit

ROOT = Path(__file__).resolve().parents[2]
DATA = Path("evals/structured_nlu/data/ai_heldout")
INPUT_PATHS = {
    "validation_dataset": DATA / "ai-internal-validation-v1-reviewed.json",
    "validation_review_ledger": DATA / "ai-internal-validation-v1-review-ledger.json",
    "validation_case_decisions": DATA / "ai-internal-validation-v1-case-decisions.json",
    "known_corpus_inventory": DATA / "known-nlu-corpus-inventory-v1.json",
}
SOURCE_ROOTS = (
    "core",
    "evals/structured_nlu",
    "llm",
    "schemas",
    "services/flow",
    "scripts",
    "experiments/as_safety_v2",
    "experiments/as_safety_v4",
)
SOURCE_FILES = (
    "experiments/nlu_current_baseline_v1/run.py",
    "experiments/nlu_current_baseline_v1/verify.py",
)
HARNESS_ROOT = "experiments/internal_validation_pair_v1"
SELECTION_RULE = "docs/portfolio/nlu_internal_validation_selection_rule_v1.md"
KIND = "ai_reviewed_internal_validation_pair_v1"
SCOPE = "ai_authored_user_adjudicated_validation_candidate_selection_only"
MODEL_SHA256 = "644b04cde835d486df33c6d4d7552ba367fcb28802fe39b6b4bb9c60b9ab6f3d"
IMAGE_DIGEST = "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
REQUEST_POLICY = {
    "endpoint": "http://127.0.0.1:18081/v1/chat/completions",
    "model_id": "kanana-q5",
    "max_tokens": 180,
    "temperature": 0,
    "repeat_penalty": 1.05,
    "stop": ["<|eot_id|>"],
    "timeout_seconds": 180,
    "retry_policy": "one_retry_after_contract_failure",
    "cache_policy": "mixed",
}
LOCAL_RUNTIME = {
    "host_port": 18081,
    "cpu_count": 2,
    "memory_bytes": 10 * 1024**3,
    "context_tokens": 4096,
    "threads": 2,
    "parallel_slots": 1,
    "restart_interval_arm_evaluations": 8,
    "docker_desktop_target_memory_bytes": 12 * 1024**3,
    "docker_host_min_memory_bytes": 23 * 1024**3 // 2,
}
PROTOCOL_KEYS = {
    "kind",
    "scope",
    "inputs",
    "known_corpus_scope",
    "policy_sha256",
    "model_sha256",
    "server_image_digest",
    "request_policy",
    "local_runtime",
    "arms",
    "harness_source_manifest",
    "selection_rule_sha256",
    "output_paths",
    "case_order",
    "pair_order",
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_json(raw: bytes) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def finite(_value: str) -> None:
        raise ValueError("non-finite JSON number")

    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=finite)


def _relative(path: str) -> Path:
    relative = Path(path)
    if not path or relative.is_absolute() or ".." in relative.parts or relative.as_posix() != path:
        raise ValueError("repository-relative path required")
    return relative


def _git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ("git", *args), cwd=root, check=True, capture_output=True, timeout=30
    ).stdout


def _frozen(root: Path, commit: str, relative: str) -> bytes:
    if not COMMIT.fullmatch(commit):
        raise ValueError("full Git commit required")
    _relative(relative)
    return _git(root, "show", f"{commit}:{relative}")


def _manifest(root: Path, commit: str, *, harness: bool = False) -> dict[str, str]:
    paths = (HARNESS_ROOT,) if harness else (*SOURCE_ROOTS, *SOURCE_FILES)
    listed = _git(root, "ls-tree", "-r", "--name-only", commit, "--", *paths)
    names = sorted(name for name in listed.decode().splitlines() if name.endswith(".py"))
    if not names or (harness and not any(name.endswith("/qualification.py") for name in names)):
        raise ValueError("source manifest is empty or misses qualification code")
    return {name: _sha(_frozen(root, commit, name)) for name in names}


def _current_source_names(root: Path) -> set[str]:
    listed = _git(root, "ls-files", "-z", "--", *SOURCE_ROOTS, *SOURCE_FILES)
    return {name for name in listed.decode().split("\0") if name.endswith(".py")}


def _known_inventory(raw: bytes, root: Path) -> set[str]:
    data = _strict_json(raw)
    if type(data) is not dict or set(data) != {
        "kind",
        "scope",
        "normalization",
        "source_files",
        "normalized_message_sha256",
    }:
        raise ValueError("known-corpus inventory fields differ")
    if (
        data["kind"] != "known_nlu_corpus_inventory_v1"
        or data["scope"] != "repository_corpus_exact_match_only"
        or data["normalization"] != "NFC+strip"
    ):
        raise ValueError("known-corpus inventory identity differs")
    files = data["source_files"]
    digests = data["normalized_message_sha256"]
    if type(files) is not dict or not files or type(digests) is not list or not digests:
        raise ValueError("known-corpus inventory is empty")
    if digests != sorted(set(digests)) or any(
        type(item) is not str or not SHA.fullmatch(item) for item in digests
    ):
        raise ValueError("known-corpus message hashes differ")
    observed_files, observed_messages = _collect_known_corpus(root)
    if files != observed_files or digests != observed_messages:
        raise ValueError("known-corpus inventory differs from repository corpus")
    return set(digests)


def _collect_known_corpus(root: Path) -> tuple[dict[str, str], list[str]]:
    """Recompute the inventory from repository JSON/JSONL `user_message` values."""
    data_root = root / "evals/structured_nlu/data"
    file_hashes = {}
    messages = set()

    def walk(value: object, collected: set[str]) -> None:
        if type(value) is dict:
            for key, item in value.items():
                if key == "user_message" and type(item) is str and item.strip():
                    normalized = unicodedata.normalize("NFC", item).strip()
                    collected.add(_sha(normalized.encode("utf-8")))
                walk(item, collected)
        elif type(value) is list:
            for item in value:
                walk(item, collected)

    for path in sorted(data_root.rglob("*")):
        if path.suffix not in {".json", ".jsonl"} or "ai-internal-validation-v1" in path.name:
            continue
        if path.name == INPUT_PATHS["known_corpus_inventory"].name:
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("known-corpus source escapes repository")
        if not path.is_file():
            continue
        raw = path.read_bytes()
        documents = (
            [_strict_json(line) for line in raw.splitlines() if line.strip()]
            if path.suffix == ".jsonl"
            else [_strict_json(raw)]
        )
        found: set[str] = set()
        for document in documents:
            walk(document, found)
        if found:
            file_hashes[path.relative_to(root).as_posix()] = _sha(raw)
            messages.update(found)
    return file_hashes, sorted(messages)


def qualify_validation(root: Path, inputs: dict[str, bytes]) -> tuple[list[str], dict[str, str]]:
    """Verify review identity, balance and known exact non-exposure."""
    if set(inputs) != set(INPUT_PATHS):
        raise ValueError("validation input set differs")
    dataset = _checked_split(
        inputs["validation_dataset"],
        inputs["validation_review_ledger"],
        inputs["validation_case_decisions"],
        DatasetSplit.VALIDATION,
    )
    if _balanced_scenarios(dataset, DatasetSplit.VALIDATION) != 2 or len(dataset.cases) != 32:
        raise ValueError("validation sampling balance differs")
    prior = _known_inventory(inputs["known_corpus_inventory"], root)
    for case in dataset.cases:
        normalized = unicodedata.normalize("NFC", case.user_message).strip()
        if _sha(normalized.encode("utf-8")) in prior:
            raise ValueError(f"known-corpus exact exposure: {case.id}")
    return [case.id for case in dataset.cases], {key: _sha(raw) for key, raw in inputs.items()}


def pair_order(case_ids: list[str]) -> list[dict[str, object]]:
    """Balance AB/BA within both in-scope and unknown groups by four-case blocks."""
    if len(case_ids) != 32 or len(set(case_ids)) != 32:
        raise ValueError("exactly 32 unique validation cases required")
    return [
        {
            "case_id": case_id,
            "arms": ["baseline", "candidate"] if index % 4 in (0, 3) else ["candidate", "baseline"],
        }
        for index, case_id in enumerate(case_ids)
    ]


def build_protocol(
    *,
    baseline_root: Path,
    baseline_commit: str,
    candidate_root: Path,
    candidate_commit: str,
    model_path: Path,
    output: Path,
    journal: Path,
    private_dir: Path,
    receipt: Path,
) -> dict:
    """Bind two clean frozen revisions and all reviewed inputs before model calls."""
    if baseline_commit == candidate_commit:
        raise ValueError("comparison requires two distinct code commits")
    if _file_sha(model_path) != MODEL_SHA256:
        raise ValueError("Q5 model file differs")
    output_paths = _output_paths(
        output, journal, private_dir, receipt, baseline_root, candidate_root
    )
    for root, commit in ((baseline_root, baseline_commit), (candidate_root, candidate_commit)):
        head = _git(root, "rev-parse", "HEAD").decode().strip()
        if root == baseline_root and head != commit:
            raise ValueError("baseline worktree HEAD differs from frozen commit")
        if root == candidate_root:
            subprocess.run(
                ("git", "merge-base", "--is-ancestor", commit, head),
                cwd=root,
                check=True,
                capture_output=True,
                timeout=30,
            )
        if _git(root, "status", "--porcelain").strip():
            raise ValueError("worktree must be clean before model calls")
    inputs = {key: (candidate_root / path).read_bytes() for key, path in INPUT_PATHS.items()}
    case_ids, input_hashes = qualify_validation(candidate_root, inputs)
    for key, path in INPUT_PATHS.items():
        relative = path.as_posix()
        if _frozen(candidate_root, candidate_commit, relative) != inputs[key]:
            raise ValueError(f"candidate input differs from frozen commit: {key}")
        if (
            key != "known_corpus_inventory"
            and _frozen(baseline_root, baseline_commit, relative) != inputs[key]
        ):
            raise ValueError(f"baseline input differs from candidate: {key}")
    selection_rule = (candidate_root / SELECTION_RULE).read_bytes()
    if _frozen(candidate_root, candidate_commit, SELECTION_RULE) != selection_rule:
        raise ValueError("selection rule differs from frozen candidate")
    baseline_manifest = _manifest(baseline_root, baseline_commit)
    candidate_manifest = _manifest(candidate_root, candidate_commit)
    if set(candidate_manifest) != _current_source_names(candidate_root):
        raise ValueError("candidate source path set changed after arm freeze")
    for relative, expected in candidate_manifest.items():
        if _file_sha(candidate_root / relative) != expected:
            raise ValueError(f"candidate source changed after arm freeze: {relative}")
    for shared in (
        "evals/structured_nlu/metrics.py",
        "evals/structured_nlu/schema.py",
        "evals/structured_nlu/ai_heldout.py",
    ):
        if baseline_manifest.get(shared) != candidate_manifest.get(shared):
            raise ValueError(f"shared evaluation source differs: {shared}")
    return {
        "kind": KIND,
        "scope": SCOPE,
        "inputs": input_hashes,
        "known_corpus_scope": "repository_corpus_exact_match_only",
        "policy_sha256": policy_sha256(),
        "model_sha256": MODEL_SHA256,
        "server_image_digest": IMAGE_DIGEST,
        "request_policy": REQUEST_POLICY,
        "local_runtime": LOCAL_RUNTIME,
        "selection_rule_sha256": _sha(selection_rule),
        "output_paths": output_paths,
        "arms": {
            "baseline": {
                "commit": baseline_commit,
                "source_manifest": baseline_manifest,
            },
            "candidate": {
                "commit": candidate_commit,
                "source_manifest": candidate_manifest,
            },
        },
        "harness_source_manifest": _manifest(
            candidate_root, _git(candidate_root, "rev-parse", "HEAD").decode().strip(), harness=True
        ),
        "case_order": case_ids,
        "pair_order": pair_order(case_ids),
    }


def _output_paths(
    output: Path, journal: Path, private_dir: Path, receipt: Path, *roots: Path
) -> dict[str, str]:
    paths = {
        "result": output.resolve(),
        "journal": journal.resolve(),
        "private_dir": private_dir.resolve(),
        "verified_receipt": receipt.resolve(),
    }
    if len(set(paths.values())) != len(paths):
        raise ValueError("paired output paths overlap")
    if any(
        left.is_relative_to(right) or right.is_relative_to(left)
        for left_key, left in paths.items()
        for right_key, right in paths.items()
        if left_key < right_key
    ):
        raise ValueError("paired output paths nest inside one another")
    for path in paths.values():
        if any(path.is_relative_to(root.resolve()) for root in roots):
            raise ValueError("paired outputs must stay outside both frozen worktrees")
    return {key: str(path) for key, path in paths.items()}


def preflight(
    *,
    protocol_path: Path,
    baseline_root: Path,
    candidate_root: Path,
    model_path: Path,
    output: Path,
    journal: Path,
    private_dir: Path,
    receipt: Path,
) -> tuple[dict, str]:
    """Only a committed, unchanged protocol may authorize a later runner."""
    raw = protocol_path.read_bytes()
    protocol = _strict_json(raw)
    if type(protocol) is not dict or set(protocol) != PROTOCOL_KEYS:
        raise ValueError("paired validation protocol fields differ")
    expected = build_protocol(
        baseline_root=baseline_root,
        baseline_commit=protocol["arms"]["baseline"]["commit"],
        candidate_root=candidate_root,
        candidate_commit=protocol["arms"]["candidate"]["commit"],
        model_path=model_path,
        output=output,
        journal=journal,
        private_dir=private_dir,
        receipt=receipt,
    )
    if protocol != expected:
        raise ValueError("paired validation protocol differs from frozen inputs")
    try:
        relative = protocol_path.resolve().relative_to(candidate_root.resolve()).as_posix()
    except ValueError as error:
        raise ValueError("protocol must be inside candidate worktree") from error
    if _git(candidate_root, "show", f"HEAD:{relative}") != raw:
        raise ValueError("paired validation protocol must be committed")
    return protocol, _sha(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--baseline-root", type=Path, required=True)
    build.add_argument("--baseline-commit", required=True)
    build.add_argument("--candidate-root", type=Path, required=True)
    build.add_argument("--candidate-commit", required=True)
    build.add_argument("--model-path", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--result", type=Path, required=True)
    build.add_argument("--journal", type=Path, required=True)
    build.add_argument("--private-dir", type=Path, required=True)
    build.add_argument("--receipt", type=Path, required=True)
    check = commands.add_parser("check")
    check.add_argument("--baseline-root", type=Path, required=True)
    check.add_argument("--candidate-root", type=Path, required=True)
    check.add_argument("--model-path", type=Path, required=True)
    check.add_argument("--protocol", type=Path, required=True)
    check.add_argument("--result", type=Path, required=True)
    check.add_argument("--journal", type=Path, required=True)
    check.add_argument("--private-dir", type=Path, required=True)
    check.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        protocol = build_protocol(
            baseline_root=args.baseline_root,
            baseline_commit=args.baseline_commit,
            candidate_root=args.candidate_root,
            candidate_commit=args.candidate_commit,
            model_path=args.model_path,
            output=args.result,
            journal=args.journal,
            private_dir=args.private_dir,
            receipt=args.receipt,
        )
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(
                protocol, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
            )
            stream.write("\n")
    else:
        protocol, digest = preflight(
            protocol_path=args.protocol,
            baseline_root=args.baseline_root,
            candidate_root=args.candidate_root,
            model_path=args.model_path,
            output=args.result,
            journal=args.journal,
            private_dir=args.private_dir,
            receipt=args.receipt,
        )
        print(
            json.dumps(
                {
                    "scope": SCOPE,
                    "protocol_sha256": digest,
                    "validation_cases": len(protocol["case_order"]),
                    "model_calls": 0,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
