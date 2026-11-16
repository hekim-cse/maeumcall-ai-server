"""Fail-closed preflight for a fresh, reviewed internal test64 pair.

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
    _category,
    _checked_split,
    policy_sha256,
)
from evals.structured_nlu.schema import DatasetSplit

ROOT = Path(__file__).resolve().parents[2]
DATA = Path("evals/structured_nlu/data/ai_heldout")
INPUT_PATHS = {
    "test_dataset": DATA / "ai-internal-test-v1-reviewed.json",
    "test_review_ledger": DATA / "ai-internal-test-v1-review-ledger.json",
    "test_case_decisions": DATA / "ai-internal-test-v1-case-decisions.json",
    "validation_dataset": DATA / "ai-internal-validation-v1-reviewed.json",
    "known_corpus_inventory": DATA / "known-nlu-corpus-inventory-v1.json",
}
SAFETY_INPUT_PATHS = {
    "safety_dataset": DATA / "ai-internal-safety16-v1-reviewed.json",
    "safety_review_ledger": DATA / "ai-internal-safety16-v1-review-ledger.json",
    "safety_case_decisions": DATA / "ai-internal-safety16-v1-case-decisions.json",
    "safety_category_ledger": DATA / "ai-internal-safety16-v1-categories.json",
    "test_dataset": INPUT_PATHS["test_dataset"],
    "validation_dataset": INPUT_PATHS["validation_dataset"],
    "known_corpus_inventory": INPUT_PATHS["known_corpus_inventory"],
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
HARNESS_ROOT = "experiments/internal_test_pair_v1"
KIND = "ai_reviewed_internal_test_pair_v1"
SCOPE = "ai_authored_user_adjudicated_fresh_internal_test_not_human_authored"
SAFETY_KIND = "ai_reviewed_internal_safety16_pair_v1"
SAFETY_SCOPE = "ai_authored_user_adjudicated_fresh_safety16_separate_from_test64"
SAFETY_CATEGORIES = ("direct", "uncertain", "other_source", "nonoccurring")
BASELINE_COMMIT = "c46c27a52bc8cfc6e11bfa62985aa6a90d6f4da3"
CANDIDATE_COMMIT = "04af27849563f7b30845441e0f8fc6ca90f876ff"
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
    "input_commit",
    "output_paths",
    "case_order",
    "pair_order",
    "bootstrap",
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
        if (
            path.suffix not in {".json", ".jsonl"}
            or "ai-internal-validation-v1" in path.name
            or "ai-internal-test-v1" in path.name
            or "ai-internal-safety16-v1" in path.name
        ):
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


def qualify_test(
    root: Path, inputs: dict[str, bytes]
) -> tuple[list[str], dict[str, str], list[tuple[str, str, str, str]]]:
    """Verify adjudication, exact corpus separation, and the 16×2×2 design.

    Exact overlap is only a screening check. A human must separately inspect
    semantic similarity, including prior model-exposed development examples.
    """
    if set(inputs) != set(INPUT_PATHS):
        raise ValueError("test input set differs")
    dataset = _checked_split(
        inputs["test_dataset"],
        inputs["test_review_ledger"],
        inputs["test_case_decisions"],
        DatasetSplit.TEST,
    )
    if _balanced_scenarios(dataset, DatasetSplit.TEST) != 4 or len(dataset.cases) != 64:
        raise ValueError("test sampling balance differs")
    prior = _known_inventory(inputs["known_corpus_inventory"], root)
    validation = _strict_json(inputs["validation_dataset"])
    if type(validation) is not dict or type(validation.get("cases")) is not list:
        raise ValueError("validation dataset format differs")
    for row in validation["cases"]:
        if type(row) is not dict or type(row.get("user_message")) is not str:
            raise ValueError("validation message missing")
        prior.add(_sha(unicodedata.normalize("NFC", row["user_message"]).strip().encode("utf-8")))
    slots: dict[tuple[str, str, str], str] = {}
    for case in dataset.cases:
        normalized = unicodedata.normalize("NFC", case.user_message).strip()
        if _sha(normalized.encode("utf-8")) in prior:
            raise ValueError(f"known/validation exact exposure: {case.id}")
        state = "greeting" if case.conversation_state == "greeting" else "later"
        scope = "in" if _category(case) == "in_scope" else "out"
        key = (case.scenario_key, state, scope)
        if key in slots:
            raise ValueError(f"test duplicate design slot: {key}")
        slots[key] = case.id
    if len(slots) != 64:
        raise ValueError("test requires one case per scenario×state×scope slot")
    ordered = sorted(
        (scenario, state, scope, case_id) for (scenario, state, scope), case_id in slots.items()
    )
    return [row[3] for row in ordered], {key: _sha(raw) for key, raw in inputs.items()}, ordered


def qualify_safety(
    root: Path, inputs: dict[str, bytes]
) -> tuple[list[str], dict[str, str], list[tuple[str, str, str, str]]]:
    """Bind a separate 4×4 safety suite; never add it to the test64 denominator."""
    if set(inputs) != set(SAFETY_INPUT_PATHS):
        raise ValueError("safety16 input set differs")
    dataset = _checked_split(
        inputs["safety_dataset"],
        inputs["safety_review_ledger"],
        inputs["safety_case_decisions"],
        DatasetSplit.TEST,
    )
    if len(dataset.cases) != 16:
        raise ValueError("safety16 requires exactly 16 reviewed cases")
    category_data = _strict_json(inputs["safety_category_ledger"])
    if type(category_data) is not dict or set(category_data) != {
        "kind",
        "dataset_sha256",
        "categories",
    }:
        raise ValueError("safety category ledger fields differ")
    if category_data["kind"] != "ai_reviewed_internal_safety16_categories_v1" or category_data[
        "dataset_sha256"
    ] != _sha(inputs["safety_dataset"]):
        raise ValueError("safety category ledger identity differs")
    rows = category_data["categories"]
    if (
        type(rows) is not list
        or len(rows) != 16
        or any(type(row) is not dict or set(row) != {"case_id", "category"} for row in rows)
    ):
        raise ValueError("safety categories must have 16 case mappings")
    category_by_id = {row["case_id"]: row["category"] for row in rows}
    if len(category_by_id) != 16 or set(category_by_id) != {case.id for case in dataset.cases}:
        raise ValueError("safety category IDs differ")
    if any(category not in SAFETY_CATEGORIES for category in category_by_id.values()):
        raise ValueError("unknown safety category")
    if any(
        sum(category == expected for category in category_by_id.values()) != 4
        for expected in SAFETY_CATEGORIES
    ):
        raise ValueError("safety category balance differs")
    prior = _known_inventory(inputs["known_corpus_inventory"], root)
    for key in ("validation_dataset", "test_dataset"):
        previous = _strict_json(inputs[key])
        if type(previous) is not dict or type(previous.get("cases")) is not list:
            raise ValueError(f"{key} format differs")
        for row in previous["cases"]:
            if type(row) is not dict or type(row.get("user_message")) is not str:
                raise ValueError(f"{key} message missing")
            prior.add(_sha(unicodedata.normalize("NFC", row["user_message"]).strip().encode()))
    seen: set[str] = set()
    for case in dataset.cases:
        if case.scenario_key != "고객센터:a/s 접수" or case.conversation_state != "greeting":
            raise ValueError("safety16 requires A/S greeting cases")
        status_field = case.labels.fields.get("safety_status")
        status_values = status_field.accepted_values if status_field is not None else ()
        category = category_by_id[case.id]
        allowed = {
            "direct": {("safety_issue",)},
            "uncertain": {()},
            "other_source": {()},
            "nonoccurring": {(), ("no_safety_issue",)},
        }[category]
        if status_values not in allowed:
            raise ValueError(f"safety16 category/gold safety_status conflict: {case.id}")
        digest = _sha(unicodedata.normalize("NFC", case.user_message).strip().encode())
        if digest in prior or digest in seen:
            raise ValueError(f"safety16 exact exposure or duplicate: {case.id}")
        seen.add(digest)
    ordered = sorted(
        (category_by_id[case.id], "greeting", "safety", case.id) for case in dataset.cases
    )
    return [item[3] for item in ordered], {key: _sha(raw) for key, raw in inputs.items()}, ordered


def pair_order(slots: list[tuple[str, str, str, str]]) -> list[dict[str, object]]:
    """One AB and one BA in each scenario×scope stratum."""
    if len(slots) != 64 or len({row[3] for row in slots}) != 64:
        raise ValueError("exactly 64 unique test cases required")
    output = []
    for _, state, scope, case_id in slots:
        if state not in {"greeting", "later"} or scope not in {"in", "out"}:
            raise ValueError("invalid test design slot")
        output.append(
            {
                "case_id": case_id,
                "arms": ["baseline", "candidate"]
                if state == "greeting"
                else ["candidate", "baseline"],
            }
        )
    return output


def safety_pair_order(slots: list[tuple[str, str, str, str]]) -> list[dict[str, object]]:
    if len(slots) != 16:
        raise ValueError("safety pair order requires 16 cases")
    counters = {category: 0 for category in SAFETY_CATEGORIES}
    result = []
    for category, _, _, case_id in slots:
        index = counters[category]
        counters[category] += 1
        result.append(
            {
                "case_id": case_id,
                "arms": ["baseline", "candidate"] if index % 2 == 0 else ["candidate", "baseline"],
            }
        )
    if any(count != 4 for count in counters.values()):
        raise ValueError("safety pair order category balance differs")
    return result


def build_protocol(
    *,
    baseline_root: Path,
    baseline_commit: str,
    candidate_root: Path,
    candidate_commit: str,
    input_commit: str,
    model_path: Path,
    output: Path,
    journal: Path,
    private_dir: Path,
    receipt: Path,
    suite: str = "test64",
) -> dict:
    """Bind two clean frozen revisions and all reviewed inputs before model calls."""
    if baseline_commit == candidate_commit:
        raise ValueError("comparison requires two distinct code commits")
    if baseline_commit != BASELINE_COMMIT or candidate_commit != CANDIDATE_COMMIT:
        raise ValueError("test arm code commits differ from preregistration")
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
    if not COMMIT.fullmatch(input_commit):
        raise ValueError("full committed input revision required")
    subprocess.run(
        (
            "git",
            "merge-base",
            "--is-ancestor",
            input_commit,
            _git(candidate_root, "rev-parse", "HEAD").decode().strip(),
        ),
        cwd=candidate_root,
        check=True,
        capture_output=True,
        timeout=30,
    )
    if suite == "test64":
        paths = INPUT_PATHS
        case_ids, input_hashes, slots = qualify_test(
            candidate_root,
            {key: (candidate_root / path).read_bytes() for key, path in INPUT_PATHS.items()},
        )
    elif suite == "safety16":
        paths = SAFETY_INPUT_PATHS
        case_ids, input_hashes, slots = qualify_safety(
            candidate_root,
            {key: (candidate_root / path).read_bytes() for key, path in SAFETY_INPUT_PATHS.items()},
        )
    else:
        raise ValueError("unknown paired suite")
    inputs = {key: (candidate_root / path).read_bytes() for key, path in paths.items()}
    for key, path in paths.items():
        relative = path.as_posix()
        if _frozen(candidate_root, input_commit, relative) != inputs[key]:
            raise ValueError(f"input differs from committed candidate data: {key}")
        if (
            key == "validation_dataset"
            and _frozen(baseline_root, baseline_commit, relative) != inputs[key]
        ):
            raise ValueError("validation dataset differs across arms")
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
    harness_manifest = _manifest(candidate_root, input_commit, harness=True)
    harness_names = {
        name
        for name in _git(candidate_root, "ls-files", "--", HARNESS_ROOT).decode().splitlines()
        if name.endswith(".py")
    }
    if set(harness_manifest) != harness_names:
        raise ValueError("test harness path set changed after input freeze")
    for relative, digest in harness_manifest.items():
        if _file_sha(candidate_root / relative) != digest:
            raise ValueError(f"test harness changed after input freeze: {relative}")
    return {
        "kind": KIND if suite == "test64" else SAFETY_KIND,
        "scope": SCOPE if suite == "test64" else SAFETY_SCOPE,
        "inputs": input_hashes,
        "known_corpus_scope": "repository_corpus_plus_validation_exact_match_only;semantic_review_separate",
        "policy_sha256": policy_sha256(),
        "model_sha256": MODEL_SHA256,
        "server_image_digest": IMAGE_DIGEST,
        "request_policy": REQUEST_POLICY,
        "local_runtime": LOCAL_RUNTIME,
        "input_commit": input_commit,
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
        "harness_source_manifest": harness_manifest,
        "case_order": case_ids,
        "pair_order": pair_order(slots) if suite == "test64" else safety_pair_order(slots),
        "bootstrap": {
            "resamples": 20000,
            "seed": 0,
            "strata": "scenario_key×scope; 32 strata with 2 paired cases each",
            "draws_per_stratum": 2,
            "metric": "candidate_minus_baseline_exact_fraction",
            "percentile": "linear_interpolation_at_p_times_(n_minus_1),_p=0.025_and_0.975",
        }
        if suite == "test64"
        else {
            "categories": list(SAFETY_CATEGORIES),
            "cases_per_category": 4,
            "direct_new_misses_allowed": 0,
            "negative_false_alarm_categories": ["other_source", "nonoccurring"],
        },
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
        raise ValueError("paired internal test protocol fields differ")
    if protocol.get("kind") == KIND:
        suite = "test64"
    elif protocol.get("kind") == SAFETY_KIND:
        suite = "safety16"
    else:
        raise ValueError("unknown paired protocol kind")
    expected = build_protocol(
        baseline_root=baseline_root,
        baseline_commit=protocol["arms"]["baseline"]["commit"],
        candidate_root=candidate_root,
        candidate_commit=protocol["arms"]["candidate"]["commit"],
        input_commit=protocol["input_commit"],
        model_path=model_path,
        output=output,
        journal=journal,
        private_dir=private_dir,
        receipt=receipt,
        suite=suite,
    )
    if protocol != expected:
        raise ValueError("paired internal test protocol differs from frozen inputs")
    try:
        relative = protocol_path.resolve().relative_to(candidate_root.resolve()).as_posix()
    except ValueError as error:
        raise ValueError("protocol must be inside candidate worktree") from error
    if _git(candidate_root, "show", f"HEAD:{relative}") != raw:
        raise ValueError("paired internal test protocol must be committed")
    return protocol, _sha(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--baseline-root", type=Path, required=True)
    build.add_argument("--baseline-commit", required=True)
    build.add_argument("--candidate-root", type=Path, required=True)
    build.add_argument("--candidate-commit", required=True)
    build.add_argument("--input-commit", required=True)
    build.add_argument("--model-path", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--result", type=Path, required=True)
    build.add_argument("--journal", type=Path, required=True)
    build.add_argument("--private-dir", type=Path, required=True)
    build.add_argument("--receipt", type=Path, required=True)
    build.add_argument("--suite", choices=("test64", "safety16"), default="test64")
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
            input_commit=args.input_commit,
            model_path=args.model_path,
            output=args.result,
            journal=args.journal,
            private_dir=args.private_dir,
            receipt=args.receipt,
            suite=args.suite,
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
                    "scope": protocol["scope"],
                    "protocol_sha256": digest,
                    "test_cases": len(protocol["case_order"]),
                    "model_calls": 0,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
