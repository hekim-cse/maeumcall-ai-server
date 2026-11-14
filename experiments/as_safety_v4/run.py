"""Frozen, local-only ES exploratory A/S event-source model runner.

The reviewed gold is loaded for scoring after calls; prompts receive only the
utterance, reviewed service target A and validated model event candidates.
No partially written journal is resumed or overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import statistics
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.transport import (
    Completion,
    RequestPolicy,
    TransportError,
    post_json_completion,
)
from experiments.as_safety_v4.cases import load_cases
from experiments.as_safety_v4.contract import (
    route_for_events,
    stage1_messages,
    stage1_schema,
    stage2_messages,
    stage2_schema,
    validate_stage1,
    validate_stage2,
)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
KIND = "as_safety_event_source_v4_exploration_v1"
SCOPE = "ai_authored_user_reviewed_exploratory_not_official_accuracy"
CASE_ORDER = tuple(f"ES{i:02}" for i in range(1, 21))
IMAGE = "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
MODEL_SHA = "644b04cde835d486df33c6d4d7552ba367fcb28802fe39b6b4bb9c60b9ab6f3d"
INPUTS = {
    "dataset": DATA / "as-safety-event-source-v4-exploration-reviewed.v1.json",
    "review": ROOT / "docs/portfolio/nlu_safety_event_source_v4_review.md",
    "field_review": ROOT / "docs/portfolio/nlu_safety_event_source_v4_field_review.md",
    "method": ROOT / "docs/portfolio/nlu_safety_event_source_v4_method.md",
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
REQUIRED_V4_SOURCES = frozenset(
    {
        "experiments/as_safety_v4/__init__.py",
        "experiments/as_safety_v4/cases.py",
        "experiments/as_safety_v4/contract.py",
        "experiments/as_safety_v4/run.py",
        "experiments/as_safety_v4/verify.py",
    }
)
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
CompletionCall = Callable[..., Completion]


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
    if not COMMIT_RE.fullmatch(commit) or not relative or relative.startswith("/"):
        raise ValueError("invalid frozen source reference")
    if ".." in Path(relative).parts:
        raise ValueError("invalid frozen source reference")
    return _git("show", f"{commit}:{relative}")


def _source_paths(commit: str) -> set[str]:
    paths: set[str] = set()
    for prefix in ("experiments/as_safety_v2", "experiments/as_safety_v4"):
        output = _git("ls-tree", "-r", "--name-only", commit, "--", prefix)
        paths.update(path for path in output.decode().splitlines() if path.endswith(".py"))
    return paths


def load_protocol(path: Path, model_path: Path) -> tuple[dict, str]:
    """Require an exact committed code/input/model identity before any request."""
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
        or protocol["case_order"] != list(CASE_ORDER)
        or protocol["server_image_digest"] != IMAGE
        or protocol["model_sha256"] != MODEL_SHA
        or digest_file(model_path) != MODEL_SHA
        or protocol["request_policy"] != REQUEST
        or protocol["local_runtime"] != RUNTIME
        or protocol["retry_policy"] != "no_retry_manual_audit_on_interruption"
        or protocol["private_output"] != "outside_repository_mode_0700_files_0600"
    ):
        raise ValueError("protocol identity differs")
    hashes = protocol["input_hashes"]
    if type(hashes) is not dict or set(hashes) != set(INPUTS):
        raise ValueError("input manifest differs")
    for key, input_path in INPUTS.items():
        relative = input_path.relative_to(ROOT).as_posix()
        frozen = _committed(commit, relative)
        expected = hashes[key]
        if type(expected) is not str or not SHA_RE.fullmatch(expected):
            raise ValueError(f"input hash differs: {key}")
        if digest(frozen) != expected or frozen != input_path.read_bytes():
            raise ValueError(f"frozen input differs: {key}")
    sources = _source_paths(commit)
    if not REQUIRED_V4_SOURCES <= sources:
        raise ValueError("required v4 source missing from frozen commit")
    manifest = protocol["source_manifest"]
    if type(manifest) is not dict or set(manifest) != sources:
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
    if _git("status", "--porcelain").strip():
        raise ValueError("checkout differs before model calls")
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
        os.fchmod(stream.fileno(), 0o600)
        if stat.S_IMODE(os.fstat(stream.fileno()).st_mode) != 0o600:
            raise ValueError("private raw file mode differs")
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(encoded), len(encoded)


def _public_span(span: dict | None) -> dict | None:
    if span is None:
        return None
    return {key: span[key] for key in ("clause_index", "start", "end", "quote_sha256")}


def _blank(*, called: bool, skip_reason: str | None = None) -> dict:
    return {
        "called": called,
        "status": "response_error" if called else "skipped",
        "skip_reason": None if called else skip_reason,
        "error_code": None,
        "error_field": None,
        "finish_reason": None,
        "latency_ms": None,
        "request_latency_ms": None,
        "raw_sha256": None,
        "raw_bytes": None,
    }


def _call(
    *,
    messages: list[dict[str, str]],
    schema: dict,
    policy: RequestPolicy,
    raw_path: Path,
    completion_call: CompletionCall,
) -> tuple[dict, str | None]:
    record = _blank(called=True)
    content = None
    started = time.perf_counter()
    try:
        response = completion_call(messages, schema, policy=policy)
    except TransportError as error:
        request_finished = time.perf_counter()
        record["error_code"] = error.code
    else:
        request_finished = time.perf_counter()
        content = response.content
        record["finish_reason"] = response.finish_reason
        record["raw_sha256"], record["raw_bytes"] = _raw(raw_path, content)
        if response.finish_reason != "stop":
            record["error_code"] = "finish_length"
    record["request_latency_ms"] = round((request_finished - started) * 1000, 3)
    # Includes private raw-output fsync; it is not the model request latency.
    record["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return record, content


def call_case(
    case: dict,
    policy: RequestPolicy,
    private_dir: Path,
    *,
    completion_call: CompletionCall = post_json_completion,
) -> dict:
    """One Stage1 and zero-to-three Stage2 calls, with no retry."""
    case_started = time.perf_counter()
    args = {
        "product_index": case["target"]["clause_index"],
        "target_mention": case["target"]["quote"],
    }
    message = case["user_message"]
    first, raw = _call(
        messages=stage1_messages(message, **args),
        schema=stage1_schema(message),
        policy=policy,
        raw_path=private_dir / f"{case['id']}-stage1.json.txt",
        completion_call=completion_call,
    )
    validated = None
    if first["error_code"] is None and raw is not None:
        try:
            validated = validate_stage1(raw, message, **args)
        except ValidationError as error:
            first.update(status="contract_error", error_code=error.code, error_field=error.field)
        else:
            first["status"] = "validated"
    first["events"] = (
        None
        if validated is None
        else [
            {"event_span": _public_span(item["event_span"]), "occurrence": item["occurrence"]}
            for item in validated["events"]
        ]
    )
    first["overflow"] = None if validated is None else validated["overflow"]
    stages: list[dict] = []
    relations: list[str | None] = []
    failed = validated is None
    if validated is not None:
        for index, event in enumerate(validated["events"], 1):
            if event["occurrence"] == "nonoccurring":
                stage = _blank(called=False, skip_reason="nonoccurring")
                stage.update(event_index=index, owner_to_target=None, hazard_owner_span=None)
                stages.append(stage)
                relations.append(None)
                continue
            stage, raw = _call(
                messages=stage2_messages(message, event, **args),
                schema=stage2_schema(message),
                policy=policy,
                raw_path=private_dir / f"{case['id']}-stage2-{index}.json.txt",
                completion_call=completion_call,
            )
            stage.update(event_index=index, owner_to_target=None, hazard_owner_span=None)
            if stage["error_code"] is None and raw is not None:
                try:
                    decision = validate_stage2(raw, message, event, **args)
                except ValidationError as error:
                    stage.update(
                        status="contract_error", error_code=error.code, error_field=error.field
                    )
                else:
                    stage.update(
                        status="validated",
                        owner_to_target=decision["owner_to_target"],
                        hazard_owner_span=_public_span(decision["hazard_owner_span"]),
                    )
            if stage["status"] != "validated":
                failed = True
            stages.append(stage)
            relations.append(stage["owner_to_target"])
    route = (
        route_for_events(
            validated["events"], relations, overflow=validated["overflow"], failed=failed
        )
        if validated is not None
        else "confirming_safety_status"
    )
    return {
        "event": "end",
        "case_id": case["id"],
        "stage1": first,
        "stage2": stages,
        "route": route,
        "request_count": int(first["called"]) + sum(int(stage["called"]) for stage in stages),
        "model_call_latency_sum_ms": round(
            first["request_latency_ms"] + sum(stage["request_latency_ms"] or 0 for stage in stages),
            3,
        ),
        "elapsed_ms": round((time.perf_counter() - case_started) * 1000, 3),
    }


def summarize(rows: list[dict], cases: list[dict]) -> dict:
    """Public development metrics; independent verifier must recompute all."""
    if len(rows) != len(cases):
        raise ValueError("case count differs")
    if tuple(row["case_id"] for row in rows) != tuple(case["id"] for case in cases):
        raise ValueError("case order differs")
    gold_events = 0
    predicted_events = 0
    exact_event_cases = 0
    occurrence_correct = 0
    relation_correct = 0
    actionable_gold_events = 0
    actionable_gold_on_exact_event_cases = 0
    other_observed_cases = 0
    false_direct_other = 0
    missed_direct_current = 0
    unnecessary_confirm = 0
    for row, case in zip(rows, cases, strict=True):
        gold = case["events"]
        gold_events += len(gold)
        actionable_gold_events += sum(event["occurrence"] != "nonoccurring" for event in gold)
        predicted = row["stage1"]["events"] or []
        predicted_events += len(predicted)
        clauses = split_clauses(case["user_message"])
        references = [
            {
                "event_span": _public_span(
                    anchor_span(event["event_span"], clauses, field="event_span")
                ),
                "occurrence": event["occurrence"],
            }
            for event in gold
        ]
        occurrence_correct += sum(item in references for item in predicted)
        if predicted == references and row["stage1"]["status"] == "validated":
            exact_event_cases += 1
            actionable_gold_on_exact_event_cases += sum(
                event["occurrence"] != "nonoccurring" for event in gold
            )
            relation_correct += sum(
                stage["status"] == "validated"
                and stage["owner_to_target"] == event["owner_to_target"]
                for stage, event in zip(row["stage2"], gold, strict=True)
                if event["occurrence"] != "nonoccurring"
            )
        expected = case["expected_route"]
        if expected == "safety_action_required" and row["route"] != expected:
            missed_direct_current += 1
        if expected == "collecting_service_request" and row["route"] == "confirming_safety_status":
            unnecessary_confirm += 1
        if expected == "collecting_service_request" and any(
            event["occurrence"] == "observed" and event["owner_to_target"] == "other"
            for event in gold
        ):
            other_observed_cases += 1
            false_direct_other += row["route"] == "safety_action_required"
    elapsed = sorted(row["elapsed_ms"] for row in rows)
    latency_p50 = statistics.median(elapsed) if elapsed else None
    latency_p95 = elapsed[math.ceil(len(elapsed) * 0.95) - 1] if elapsed else None
    return {
        "cases": len(rows),
        "gold_event_count": gold_events,
        "predicted_event_count": predicted_events,
        "stage1_exact_event_cases": exact_event_cases,
        "occurrence_correct_event_count": occurrence_correct,
        "actionable_gold_event_count": actionable_gold_events,
        "actionable_gold_on_exact_event_cases": actionable_gold_on_exact_event_cases,
        "relation_correct_on_exact_event_cases": relation_correct,
        "route_correct": sum(
            row["route"] == case["expected_route"] for row, case in zip(rows, cases, strict=True)
        ),
        "other_observed_cases": other_observed_cases,
        "false_direct_other": false_direct_other,
        "missed_direct_current": missed_direct_current,
        "unnecessary_confirm": unnecessary_confirm,
        "overflow_cases": sum(row["stage1"]["overflow"] is True for row in rows),
        "stage1_errors": sum(row["stage1"]["status"] != "validated" for row in rows),
        "stage2_errors": sum(
            stage["called"] and stage["status"] != "validated"
            for row in rows
            for stage in row["stage2"]
        ),
        "request_count": sum(row["request_count"] for row in rows),
        "stage1_valid": sum(row["stage1"]["status"] == "validated" for row in rows),
        "stage2_valid": sum(
            stage["status"] == "validated" for row in rows for stage in row["stage2"]
        ),
        "case_elapsed_p50_ms": round(latency_p50, 3) if latency_p50 is not None else None,
        "case_elapsed_p95_ms": round(latency_p95, 3) if latency_p95 is not None else None,
    }


def run(
    args: argparse.Namespace, *, completion_call: CompletionCall = post_json_completion
) -> None:
    if args.output.exists() or args.private_dir.exists():
        raise FileExistsError("existing output requires manual audit; never overwrite")
    protocol, protocol_sha = load_protocol(args.protocol, args.model_path)
    cases = load_cases(INPUTS["dataset"])
    if tuple(case["id"] for case in cases) != CASE_ORDER:
        raise ValueError("case order differs")
    verify_container(args.container_name, args.model_path)
    if args.private_dir.resolve().is_relative_to(ROOT):
        raise ValueError("private raw output must stay outside repository")
    args.private_dir.mkdir(mode=0o700, parents=False)
    args.private_dir.chmod(0o700)
    if stat.S_IMODE(args.private_dir.stat().st_mode) != 0o700:
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
    rows: list[dict] = []
    with args.output.open("x", encoding="utf-8") as stream:
        _append(stream, {"event": "header", "protocol_sha256": protocol_sha})
        for case in cases:
            _append(stream, {"event": "begin", "case_id": case["id"]})
            end = call_case(case, policy, args.private_dir, completion_call=completion_call)
            _append(stream, end)
            rows.append(end)
        _append(stream, {"event": "summary", **summarize(rows, cases)})


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
