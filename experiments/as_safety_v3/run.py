"""Paired Stage2-only A/S owner-link diagnostic on frozen, exposed v2 cases.

The v2 Stage1 raw outputs are verified and replayed; only Stage2 calls the
local model. This runner is for development diagnosis, not service routing or
an independent accuracy claim. A partially written journal is never resumed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

from experiments.as_safety_v2.cases import CASE_IDS, load_development_cases
from experiments.as_safety_v2.extraction import validate_stage1
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.transport import RequestPolicy, TransportError, post_json_completion
from experiments.as_safety_v3.relation import stage2_messages, stage2_schema, validate_stage2

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
KIND = "as_safety_owner_link_v3_stage2_paired_v1"
SCOPE = "already_exposed_ai_authored_conditional_stage2_development_only"
CASE_ORDER = "RE01-RE06,RE08-RE11,V01-V08,V10,V12,V14,V16"
IMAGE = "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
MODEL_SHA = "644b04cde835d486df33c6d4d7552ba367fcb28802fe39b6b4bb9c60b9ab6f3d"
BASELINE_PROTOCOL = DATA / "as-safety-extraction-v2-development-protocol.v1.json"
BASELINE_JOURNAL = DATA / "as-safety-extraction-v2-development-journal.v1.jsonl"
INPUTS = {
    "re_dataset": DATA / "as-safety-relation-fresh-reviewed.v1.json",
    "v_dataset": DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
    "labels": DATA / "as-safety-extraction-v2-development-labels.v1.json",
    "spans": DATA / "as-safety-oracle-relation-spans-reviewed.v1.json",
    "subject": DATA / "as-safety-owner-evidence-reviewed.v1.json",
    "owner_review": ROOT / "docs/portfolio/nlu_safety_owner_resolution_review.md",
    "baseline_protocol": BASELINE_PROTOCOL,
    "baseline_journal": BASELINE_JOURNAL,
}
RUNTIME = {
    "host_port": 18081,
    "cpu_count": 2,
    "memory_bytes": 4 * 1024**3,
    "context_tokens": 4096,
    "threads": 2,
    "parallel_slots": 1,
}
SERVER_ARGS = [
    "-m",
    "/models/kanana.gguf",
    "-c",
    "4096",
    "-t",
    "2",
    "-np",
    "1",
    "--host",
    "0.0.0.0",
    "--port",
    "8080",
]
REQUEST = {
    "max_tokens": 320,
    "temperature": 0,
    "repeat_penalty": 1.05,
    "stop": ["<|eot_id|>"],
    "timeout_seconds": 180,
    "seed": 0,
}
PROTOCOL_FIELDS = {
    "kind",
    "claim_scope",
    "case_order",
    "frozen_code_commit",
    "input_hashes",
    "source_manifest",
    "model_sha256",
    "server_image_digest",
    "request_policy",
    "local_runtime",
    "retry_policy",
    "private_output",
}
REQUIRED_V3_SOURCES = frozenset(
    {
        "experiments/as_safety_v3/__init__.py",
        "experiments/as_safety_v3/relation.py",
        "experiments/as_safety_v3/run.py",
        "experiments/as_safety_v3/verify.py",
    }
)
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _git(*args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=ROOT, check=True, capture_output=True).stdout


def _committed(commit: str, relative: str) -> bytes:
    if not COMMIT_RE.fullmatch(commit):
        raise ValueError("frozen commit is invalid")
    if not relative or relative.startswith("/") or ".." in Path(relative).parts:
        raise ValueError("frozen path is invalid")
    return _git("show", f"{commit}:{relative}")


def _source_paths(commit: str) -> set[str]:
    paths: set[str] = set()
    for prefix in ("experiments/as_safety_v2", "experiments/as_safety_v3"):
        output = _git("ls-tree", "-r", "--name-only", commit, "--", prefix)
        paths.update(path for path in output.decode().splitlines() if path.endswith(".py"))
    return paths


def load_protocol(path: Path, model_path: Path) -> tuple[dict, str]:
    """Reject source, input, model, policy or checkout drift before any call."""
    raw = path.read_bytes()
    protocol = json.loads(raw)
    if type(protocol) is not dict or set(protocol) != PROTOCOL_FIELDS:
        raise ValueError("protocol fields differ")
    commit = protocol["frozen_code_commit"]
    if (
        type(commit) is not str
        or not COMMIT_RE.fullmatch(commit)
        or protocol["kind"] != KIND
        or protocol["claim_scope"] != SCOPE
        or protocol["case_order"] != CASE_ORDER
        or protocol["server_image_digest"] != IMAGE
        or protocol["model_sha256"] != MODEL_SHA
        or digest_file(model_path) != MODEL_SHA
        or protocol["request_policy"] != REQUEST
        or protocol["local_runtime"] != RUNTIME
        or protocol["retry_policy"] != "no_retry_manual_audit_on_interruption"
        or protocol["private_output"] != "outside_repository_mode_0700_files_0600"
    ):
        raise ValueError("protocol identity differs")
    if type(protocol["input_hashes"]) is not dict or set(protocol["input_hashes"]) != set(INPUTS):
        raise ValueError("input manifest differs")
    for key, input_path in INPUTS.items():
        relative = input_path.relative_to(ROOT).as_posix()
        frozen = _committed(commit, relative)
        expected = protocol["input_hashes"][key]
        if type(expected) is not str or not SHA_RE.fullmatch(expected):
            raise ValueError(f"input hash differs: {key}")
        if digest(frozen) != expected or frozen != input_path.read_bytes():
            raise ValueError(f"frozen input differs: {key}")
    manifest = protocol["source_manifest"]
    frozen_sources = _source_paths(commit)
    if not REQUIRED_V3_SOURCES <= frozen_sources:
        raise ValueError("required v3 source missing from frozen commit")
    if type(manifest) is not dict or set(manifest) != frozen_sources:
        raise ValueError("source manifest differs")
    for relative, expected in manifest.items():
        if type(expected) is not str or not SHA_RE.fullmatch(expected):
            raise ValueError(f"source hash differs: {relative}")
        frozen = _committed(commit, relative)
        if digest(frozen) != expected or frozen != (ROOT / relative).read_bytes():
            raise ValueError(f"frozen source differs: {relative}")
    relative_protocol = path.resolve().relative_to(ROOT).as_posix()
    if _git("show", f"HEAD:{relative_protocol}") != raw:
        raise ValueError("protocol must be committed before model calls")
    if _git("status", "--porcelain", "--untracked-files=no").strip():
        raise ValueError("tracked checkout differs before model calls")
    return protocol, digest(raw)


def verify_container(name: str, model_path: Path) -> None:
    observed = json.loads(
        subprocess.run(
            ("docker", "inspect", name), check=True, capture_output=True, text=True
        ).stdout
    )[0]
    host = observed["HostConfig"]
    if not observed["State"]["Running"] or observed["Image"] != IMAGE:
        raise ValueError("model server image differs")
    if host["NanoCpus"] != 2_000_000_000 or host["Memory"] != RUNTIME["memory_bytes"]:
        raise ValueError("model server resource bounds differ")
    if host["PortBindings"] != {"8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18081"}]}:
        raise ValueError("model server port differs")
    if observed["Config"]["Cmd"] != SERVER_ARGS:
        raise ValueError("model server arguments differ")
    if not any(
        mount["Source"] == str(model_path.resolve())
        and mount["Destination"] == "/models/kanana.gguf"
        and not mount["RW"]
        for mount in observed["Mounts"]
    ):
        raise ValueError("model mount differs")


def _append(stream, row: dict) -> None:
    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def _raw(path: Path, content: str) -> tuple[str, int]:
    encoded = content.encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(encoded), len(encoded)


def _public_span(span: dict | None) -> dict | None:
    if span is None:
        return None
    return {key: span[key] for key in ("clause_index", "start", "end", "quote_sha256")}


def load_baseline(private_dir: Path) -> list[tuple[dict, dict, dict | None]]:
    """Audit all 22 old raw Stage1 files and return their validated values."""
    if private_dir.resolve().is_relative_to(ROOT):
        raise ValueError("baseline private raw output must stay outside repository")
    if private_dir.stat().st_mode & 0o077:
        raise ValueError("baseline private directory permissions differ")
    rows = [json.loads(line) for line in BASELINE_JOURNAL.read_text(encoding="utf-8").splitlines()]
    if len(rows) != 45 or rows[0] != {
        "event": "header",
        "protocol_sha256": digest(BASELINE_PROTOCOL.read_bytes()),
    }:
        raise ValueError("baseline journal shape differs")
    cases = load_development_cases(
        re_dataset=INPUTS["re_dataset"],
        v_dataset=INPUTS["v_dataset"],
        labels_path=INPUTS["labels"],
        spans_path=INPUTS["spans"],
        subject_path=INPUTS["subject"],
        owner_review_path=INPUTS["owner_review"],
    )
    if tuple(case["id"] for case in cases) != CASE_IDS:
        raise ValueError("baseline case order differs")
    paired = []
    eligible = 0
    for index, case in enumerate(cases):
        case_id = case["id"]
        if rows[1 + index * 2] != {"event": "begin", "case_id": case_id}:
            raise ValueError("baseline begin row differs")
        end = rows[2 + index * 2]
        if end.get("event") != "end" or end.get("case_id") != case_id:
            raise ValueError("baseline end row differs")
        first = end["stage1"]
        if first.get("called") is not True or first.get("finish_reason") != "stop":
            raise ValueError("baseline Stage1 call differs")
        raw_path = private_dir / f"{case_id}-stage1.json.txt"
        if raw_path.stat().st_mode & 0o077:
            raise ValueError("baseline raw file permissions differ")
        raw = raw_path.read_bytes()
        if digest(raw) != first.get("raw_sha256") or len(raw) != first.get("raw_bytes"):
            raise ValueError("baseline Stage1 raw differs")
        args = {
            "product_index": case["target"]["clause_index"],
            "target_mention": case["target"]["quote"],
        }
        try:
            validated = validate_stage1(raw.decode("utf-8"), case["user_message"], **args)
        except ValidationError as error:
            if first.get("status") != "contract_error" or (
                first.get("error_code"),
                first.get("error_field"),
            ) != (error.code, error.field):
                raise ValueError("baseline Stage1 error differs") from None
            validated = None
        else:
            expected_spans = {
                name: _public_span(validated[name])
                for name in ("event_span", "subject_span", "owner_span")
            }
            if (
                first.get("status") != "validated"
                or first.get("spans") != expected_spans
                or first.get("owner_kind") != validated["owner_kind"]
                or validated["event_span"] is None
                or validated["subject_span"] is None
            ):
                raise ValueError("baseline Stage1 validated value differs")
            eligible += 1
        paired.append((case, first, validated))
    if eligible != 20 or len(paired) != 22:
        raise ValueError("baseline Stage1 denominator differs")
    return paired


def _blank_stage2(*, called: bool) -> dict:
    return {
        "called": called,
        "status": "response_error" if called else "skipped",
        "skip_reason": None if called else "baseline_stage1_invalid",
        "error_code": None,
        "error_field": None,
        "finish_reason": None,
        "latency_ms": None,
        "raw_sha256": None,
        "raw_bytes": None,
        "model_link": None,
        "effective_relation": None,
        "hazard_owner_span": None,
    }


def call_case(
    case: dict,
    baseline_stage1: dict,
    validated: dict | None,
    policy: RequestPolicy,
    private_dir: Path,
) -> dict:
    stage2 = _blank_stage2(called=validated is not None)
    started = time.perf_counter()
    if validated is not None:
        args = {
            "product_index": case["target"]["clause_index"],
            "target_mention": case["target"]["quote"],
        }
        try:
            response = post_json_completion(
                stage2_messages(case["user_message"], validated, **args),
                stage2_schema(case["user_message"]),
                policy=policy,
            )
        except TransportError as error:
            stage2["error_code"] = error.code
        else:
            stage2["finish_reason"] = response.finish_reason
            stage2["raw_sha256"], stage2["raw_bytes"] = _raw(
                private_dir / f"{case['id']}-stage2.json.txt", response.content
            )
            if response.finish_reason != "stop":
                stage2["error_code"] = "finish_length"
            else:
                try:
                    decision = validate_stage2(
                        response.content, case["user_message"], validated, **args
                    )
                except ValidationError as error:
                    stage2.update(
                        {
                            "status": "contract_error",
                            "error_code": error.code,
                            "error_field": error.field,
                        }
                    )
                else:
                    stage2.update(
                        {
                            "status": "validated",
                            "model_link": decision["model_link"],
                            "effective_relation": decision["effective_relation"],
                            "hazard_owner_span": _public_span(decision["hazard_owner_span"]),
                        }
                    )
        stage2["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    relation = stage2["effective_relation"] if stage2["status"] == "validated" else "unknown"
    return {
        "event": "end",
        "case_id": case["id"],
        "baseline_stage1": baseline_stage1,
        "stage2": stage2,
        "source_relation": relation,
        "stage2_elapsed_ms": stage2["latency_ms"],
    }


def run(args: argparse.Namespace) -> None:
    if args.output.exists() or args.private_dir.exists():
        raise FileExistsError("existing output requires manual audit; never overwrite")
    protocol, protocol_sha = load_protocol(args.protocol, args.model_path)
    paired = load_baseline(args.baseline_private_dir)
    verify_container(args.container_name, args.model_path)
    if args.private_dir.resolve().is_relative_to(ROOT):
        raise ValueError("private raw output must stay outside repository")
    args.private_dir.mkdir(mode=0o700, parents=False)
    if args.private_dir.stat().st_mode & 0o077:
        raise ValueError("private output permissions differ")
    request = protocol["request_policy"]
    policy = RequestPolicy(
        max_tokens=request["max_tokens"],
        temperature=request["temperature"],
        repeat_penalty=request["repeat_penalty"],
        stop=tuple(request["stop"]),
        timeout_seconds=request["timeout_seconds"],
        seed=request["seed"],
    )
    with args.output.open("x", encoding="utf-8") as stream:
        _append(stream, {"event": "header", "protocol_sha256": protocol_sha})
        for case, first, validated in paired:
            _append(stream, {"event": "begin", "case_id": case["id"]})
            _append(stream, call_case(case, first, validated, policy, args.private_dir))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--baseline-private-dir", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--private-dir", required=True, type=Path)
    parser.add_argument("--container-name", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
