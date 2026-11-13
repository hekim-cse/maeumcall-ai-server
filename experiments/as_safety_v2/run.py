"""Run the frozen, development-only A/S E/B/C extraction experiment."""

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
from experiments.as_safety_v2.extraction import stage1_messages, stage1_schema, validate_stage1
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.relation import stage2_messages, stage2_schema, validate_stage2
from experiments.as_safety_v2.transport import (
    MODEL_ID,
    RequestPolicy,
    TransportError,
    post_json_completion,
)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
IMAGE = "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
KIND = "as_safety_extraction_v2_development_v1"
SCOPE = "already_exposed_ai_authored_a_only_development_only"
CASE_ORDER = "RE01-RE06,RE08-RE11,V01-V08,V10,V12,V14,V16"
INPUTS = {
    "re_dataset": DATA / "as-safety-relation-fresh-reviewed.v1.json",
    "v_dataset": DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
    "labels": DATA / "as-safety-extraction-v2-development-labels.v1.json",
    "spans": DATA / "as-safety-oracle-relation-spans-reviewed.v1.json",
    "subject": DATA / "as-safety-owner-evidence-reviewed.v1.json",
    "owner_review": ROOT / "docs/portfolio/nlu_safety_owner_resolution_review.md",
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
RUNTIME = {
    "host_port": 18081,
    "cpu_count": 2,
    "memory_bytes": 4 * 1024**3,
    "context_tokens": 4096,
    "threads": 2,
    "parallel_slots": 1,
}


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
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("frozen commit is invalid")
    if relative.startswith("/") or ".." in Path(relative).parts or not relative:
        raise ValueError("frozen path is invalid")
    return _git("show", f"{commit}:{relative}")


def _source_paths(commit: str) -> set[str]:
    output = _git("ls-tree", "-r", "--name-only", commit, "experiments/as_safety_v2")
    return {line for line in output.decode().splitlines() if line.endswith(".py")}


def load_protocol(path: Path, model_path: Path) -> tuple[dict, str]:
    """Require committed frozen code and complete local package before calls."""
    payload = path.read_bytes()
    protocol = json.loads(payload)
    if set(protocol) != {
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
    }:
        raise ValueError("protocol fields differ")
    commit = protocol["frozen_code_commit"]
    if (
        protocol["kind"] != KIND
        or protocol["claim_scope"] != SCOPE
        or protocol["case_order"] != CASE_ORDER
        or protocol["server_image_digest"] != IMAGE
        or protocol["local_runtime"] != RUNTIME
        or protocol["retry_policy"] != "no_retry_manual_audit_on_interruption"
        or protocol["private_output"] != "outside_repository_mode_0700_files_0600"
        or not isinstance(protocol["model_sha256"], str)
        or digest_file(model_path) != protocol["model_sha256"]
    ):
        raise ValueError("protocol identity differs")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("frozen commit differs")
    if set(protocol["input_hashes"]) != set(INPUTS):
        raise ValueError("input manifest differs")
    if set(protocol["source_manifest"]) != _source_paths(commit):
        raise ValueError("source manifest differs")
    for key, input_path in INPUTS.items():
        relative = input_path.relative_to(ROOT).as_posix()
        frozen = _committed(commit, relative)
        if digest(frozen) != protocol["input_hashes"][key] or frozen != input_path.read_bytes():
            raise ValueError(f"frozen input differs: {key}")
    for relative, expected in protocol["source_manifest"].items():
        frozen = _committed(commit, relative)
        if digest(frozen) != expected or frozen != (ROOT / relative).read_bytes():
            raise ValueError(f"frozen source differs: {relative}")
    expected_policy = {
        "max_tokens": 320,
        "temperature": 0,
        "repeat_penalty": 1.05,
        "stop": ["<|eot_id|>"],
        "timeout_seconds": 180,
        "seed": 0,
    }
    if protocol["request_policy"] != expected_policy:
        raise ValueError("request policy differs")
    relative_protocol = path.resolve().relative_to(ROOT).as_posix()
    if _git("show", f"HEAD:{relative_protocol}") != payload:
        raise ValueError("protocol must be committed before model calls")
    if _git("status", "--porcelain", "--untracked-files=no").strip():
        raise ValueError("tracked checkout differs before model calls")
    return protocol, digest(payload)


def verify_container(name: str, model_path: Path) -> None:
    observed = json.loads(_docker_inspect(name))[0]
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
        and mount["Destination"] == MODEL_ID
        and not mount["RW"]
        for mount in observed["Mounts"]
    ):
        raise ValueError("model mount differs")


def _docker_inspect(name: str) -> str:
    return subprocess.run(
        ("docker", "inspect", name), check=True, capture_output=True, text=True
    ).stdout


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


def _blank_stage1() -> dict:
    return {
        "called": True,
        "status": "response_error",
        "error_code": None,
        "error_field": None,
        "finish_reason": None,
        "latency_ms": None,
        "raw_sha256": None,
        "raw_bytes": None,
        "spans": None,
        "owner_kind": None,
    }


def _blank_stage2(*, called: bool) -> dict:
    return {
        "called": called,
        "status": "response_error" if called else "skipped",
        "skip_reason": None,
        "error_code": None,
        "error_field": None,
        "finish_reason": None,
        "latency_ms": None,
        "raw_sha256": None,
        "raw_bytes": None,
        "model_relation": None,
        "effective_relation": None,
        "distinct_evidence_span": None,
    }


def _public_span(span: dict | None) -> dict | None:
    if span is None:
        return None
    return {key: span[key] for key in ("clause_index", "start", "end", "quote_sha256")}


def _invoke(messages: list[dict], schema: dict, policy: RequestPolicy, raw_path: Path):
    started = time.perf_counter()
    try:
        response = post_json_completion(messages, schema, policy=policy)
    except TransportError as error:
        return None, error.code, None, None, None, round((time.perf_counter() - started) * 1000, 3)
    raw_hash, raw_bytes = _raw(raw_path, response.content)
    error_code = None if response.finish_reason == "stop" else "finish_length"
    latency = round((time.perf_counter() - started) * 1000, 3)
    return response, error_code, response.finish_reason, raw_hash, raw_bytes, latency


def call_case(case: dict, policy: RequestPolicy, private_dir: Path) -> dict:
    started = time.perf_counter()
    target = case["target"]
    target_args = {"product_index": target["clause_index"], "target_mention": target["quote"]}
    first = _blank_stage1()
    second = _blank_stage2(called=False)
    second["skip_reason"] = "stage1_invalid"
    response, error, finish, raw_hash, raw_bytes, latency = _invoke(
        stage1_messages(case["user_message"], **target_args),
        stage1_schema(case["user_message"]),
        policy,
        private_dir / f"{case['id']}-stage1.json.txt",
    )
    first.update(
        {
            "error_code": error,
            "finish_reason": finish,
            "raw_sha256": raw_hash,
            "raw_bytes": raw_bytes,
            "latency_ms": latency,
        }
    )
    validated = None
    if error is None:
        try:
            validated = validate_stage1(response.content, case["user_message"], **target_args)
        except ValidationError as issue:
            first.update(
                {"status": "contract_error", "error_code": issue.code, "error_field": issue.field}
            )
        else:
            first["status"] = "validated"
            first["spans"] = {
                key: _public_span(validated[key])
                for key in ("event_span", "subject_span", "owner_span")
            }
            first["owner_kind"] = validated["owner_kind"]
    if first["status"] == "validated":
        if any(validated[key] is None for key in ("event_span", "subject_span", "owner_span")):
            second["skip_reason"] = "missing_event_subject_owner"
        else:
            second = _blank_stage2(called=True)
            response2, error2, finish2, hash2, bytes2, latency2 = _invoke(
                stage2_messages(case["user_message"], validated, **target_args),
                stage2_schema(case["user_message"]),
                policy,
                private_dir / f"{case['id']}-stage2.json.txt",
            )
            second.update(
                {
                    "error_code": error2,
                    "finish_reason": finish2,
                    "raw_sha256": hash2,
                    "raw_bytes": bytes2,
                    "latency_ms": latency2,
                }
            )
            if error2 is None:
                try:
                    decision = validate_stage2(
                        response2.content, case["user_message"], validated, **target_args
                    )
                except ValidationError as issue:
                    second.update(
                        {
                            "status": "contract_error",
                            "error_code": issue.code,
                            "error_field": issue.field,
                        }
                    )
                else:
                    second["status"] = "validated"
                    second["model_relation"] = decision["model_relation"]
                    second["effective_relation"] = decision["effective_relation"]
                    second["distinct_evidence_span"] = _public_span(
                        decision["distinct_evidence_span"]
                    )
    relation = second["effective_relation"] if second["status"] == "validated" else "unknown"
    route = (
        "collecting_service_request"
        if relation == "other"
        else "safety_action_required"
        if relation == "current" and case["event_status"] == "observed"
        else "confirming_safety_status"
    )
    return {
        "event": "end",
        "case_id": case["id"],
        "stage1": first,
        "stage2": second,
        "source_relation": relation,
        "route": route,
        "total_latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def run(args: argparse.Namespace) -> None:
    if args.output.exists() or args.private_dir.exists():
        raise FileExistsError("existing output requires manual audit; never overwrite")
    _, protocol_sha = load_protocol(args.protocol, args.model_path)
    cases = load_development_cases(
        re_dataset=INPUTS["re_dataset"],
        v_dataset=INPUTS["v_dataset"],
        labels_path=INPUTS["labels"],
        spans_path=INPUTS["spans"],
        subject_path=INPUTS["subject"],
        owner_review_path=INPUTS["owner_review"],
    )
    if tuple(case["id"] for case in cases) != CASE_IDS:
        raise ValueError("development cases differ")
    verify_container(args.container_name, args.model_path)
    if args.private_dir.resolve().is_relative_to(ROOT):
        raise ValueError("private raw output must stay outside repository")
    args.private_dir.mkdir(mode=0o700, parents=False)
    if args.private_dir.stat().st_mode & 0o077:
        raise ValueError("private output permissions differ")
    policy = RequestPolicy()
    with args.output.open("x", encoding="utf-8") as stream:
        _append(stream, {"event": "header", "protocol_sha256": protocol_sha})
        for case in cases:
            _append(stream, {"event": "begin", "case_id": case["id"]})
            _append(stream, call_case(case, policy, args.private_dir))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--private-dir", required=True, type=Path)
    parser.add_argument("--container-name", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
