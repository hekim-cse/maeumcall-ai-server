"""Run the frozen, local-only ES E→B extraction diagnostic once per event."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from experiments.as_safety_atomic_edges_v1.event_owner import (
    event_owner_messages,
    event_owner_schema,
)
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.transport import (
    Completion,
    RequestPolicy,
    TransportError,
    post_json_completion,
)
from experiments.as_safety_v4 import run as v4

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
INPUTS = {
    "dataset": DATA / "as-safety-event-source-v4-exploration-reviewed.v1.json",
    "utterance_review": ROOT / "docs/portfolio/nlu_safety_event_source_v4_review.md",
    "field_review": ROOT / "docs/portfolio/nlu_safety_event_source_v4_field_review.md",
    "method": ROOT / "docs/portfolio/nlu_safety_atomic_edge_v1_method.md",
    "edge_review": ROOT / "docs/portfolio/nlu_safety_evidence_graph_v1_field_review.md",
}
SOURCE_PATHS = {
    "experiments/as_safety_atomic_edges_v1/event_owner.py",
    "experiments/as_safety_atomic_edges_v1/run.py",
    "experiments/as_safety_atomic_edges_v1/verify.py",
    "experiments/as_safety_v2/evidence_graph.py",
    "experiments/as_safety_v2/extraction.py",
    "experiments/as_safety_v2/json_contract.py",
    "experiments/as_safety_v2/quotes.py",
    "experiments/as_safety_v2/transport.py",
    "experiments/as_safety_v4/cases.py",
    "experiments/as_safety_v4/contract.py",
    "experiments/as_safety_v4/run.py",
}
KIND = "as_safety_atomic_edge_v1_development_v1"
SCOPE = "already_exposed_ai_authored_user_reviewed_es_development_diagnostic_only"
CASE_ORDER = tuple(f"ES{index:02}" for index in range(1, 21))
CALL_ORDER = tuple(
    f"ES{case:02}:{event}"
    for case, event in (
        [(index, 1) for index in range(1, 6)]
        + [(6, 1), (6, 2)]
        + [(index, 1) for index in range(7, 16)]
        + [(index, 1) for index in range(16, 19)]
    )
)
SKIP_ORDER = ("ES15:2", "ES19:1", "ES20:1")
IMAGE = "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
MODEL_SHA = "644b04cde835d486df33c6d4d7552ba367fcb28802fe39b6b4bb9c60b9ab6f3d"
ENDPOINT = "http://127.0.0.1:18081/v1/chat/completions"
MODEL_ID = "/models/kanana.gguf"
RUNTIME = {
    "host_port": 18081,
    "cpu_count": 2,
    "memory_bytes": 4 * 1024**3,
    "context_tokens": 4096,
    "threads": 2,
    "parallel_slots": 1,
}
SERVER_ARGS = (
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
)
REQUEST_POLICY = {
    "max_tokens": 320,
    "temperature": 0,
    "repeat_penalty": 1.05,
    "stop": ["<|eot_id|>"],
    "timeout_seconds": 180,
    "seed": 0,
}
RETRY_POLICY = "no_retry_manual_audit_on_interruption"
PRIVATE_OUTPUT = "outside_repository_mode_0700_files_0600"
PROTOCOL_FIELDS = {
    "kind",
    "claim_scope",
    "case_order",
    "call_order",
    "skip_order",
    "frozen_code_commit",
    "input_hashes",
    "source_manifest",
    "model_sha256",
    "server_image_digest",
    "endpoint",
    "model_id",
    "server_args",
    "local_runtime",
    "request_policy",
    "retry_policy",
    "private_output",
    "score_scope",
}
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
CompletionCall = Callable[..., Completion]


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


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
    result = set()
    for relative in SOURCE_PATHS:
        _committed(commit, relative)
        result.add(relative)
    return result


def _expected_protocol() -> dict:
    return {
        "kind": KIND,
        "claim_scope": SCOPE,
        "case_order": list(CASE_ORDER),
        "call_order": list(CALL_ORDER),
        "skip_order": list(SKIP_ORDER),
        "model_sha256": MODEL_SHA,
        "server_image_digest": IMAGE,
        "endpoint": ENDPOINT,
        "model_id": MODEL_ID,
        "server_args": list(SERVER_ARGS),
        "local_runtime": RUNTIME,
        "request_policy": REQUEST_POLICY,
        "retry_policy": RETRY_POLICY,
        "private_output": PRIVATE_OUTPUT,
        "score_scope": "event_owner_only; no B_to_A scoring; no route calculation",
    }


def load_protocol(path: Path, model_path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    protocol = json.loads(raw)
    if type(protocol) is not dict or set(protocol) != PROTOCOL_FIELDS:
        raise ValueError("protocol fields differ")
    expected = _expected_protocol()
    if any(protocol.get(key) != value for key, value in expected.items()):
        raise ValueError("protocol identity differs")
    commit = protocol.get("frozen_code_commit")
    if type(commit) is not str or not COMMIT_RE.fullmatch(commit):
        raise ValueError("frozen code commit differs")
    if not model_path.is_file() or digest_file(model_path) != MODEL_SHA:
        raise ValueError("model file is missing or its SHA-256 differs")
    if type(protocol["input_hashes"]) is not dict or set(protocol["input_hashes"]) != set(INPUTS):
        raise ValueError("input manifest paths differ")
    for key, source in INPUTS.items():
        relative = source.relative_to(ROOT).as_posix()
        frozen = _committed(commit, relative)
        expected_sha = protocol["input_hashes"][key]
        if (
            type(expected_sha) is not str
            or not SHA_RE.fullmatch(expected_sha)
            or digest(frozen) != expected_sha
            or source.read_bytes() != frozen
        ):
            raise ValueError(f"frozen input differs: {key}")
    manifest = protocol["source_manifest"]
    if type(manifest) is not dict or set(manifest) != _source_paths(commit):
        raise ValueError("source manifest paths differ")
    for relative, expected_sha in manifest.items():
        frozen = _committed(commit, relative)
        if (
            type(expected_sha) is not str
            or not SHA_RE.fullmatch(expected_sha)
            or digest(frozen) != expected_sha
            or (ROOT / relative).read_bytes() != frozen
        ):
            raise ValueError(f"frozen source differs: {relative}")
    relative_protocol = path.resolve().relative_to(ROOT).as_posix()
    if _git("show", f"HEAD:{relative_protocol}") != raw:
        raise ValueError("protocol must be committed before model calls")
    if _git("status", "--porcelain").strip():
        raise ValueError("checkout must be clean before model calls")
    return protocol, digest(raw)


def _request_projection(case: dict) -> dict:
    """Keep only A and the event inputs; gold fields never enter a call object."""
    events = [
        {
            "event_index": index,
            "event_span": event["event_span"],
            "occurrence": event["occurrence"],
        }
        for index, event in enumerate(case["events"], 1)
    ]
    return {
        "case_id": case["id"],
        "user_message": case["user_message"],
        "product_index": case["target"]["clause_index"],
        "target_mention": case["target"]["quote"],
        "events": events,
    }


def load_request_cases(path: Path) -> list[dict]:
    """Project only source text, A, E and occurrence into inference inputs."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if type(payload) is not dict or set(payload) != {
        "kind",
        "provenance",
        "review_status",
        "review_date",
        "source_sha256",
        "cases",
    }:
        raise ValueError("reviewed dataset fields differ")
    if (
        payload["kind"] != "as_safety_event_source_v4_exploration_reviewed_v1"
        or payload["provenance"] != "ai_authored_user_reviewed_exploration"
        or payload["review_status"] != "owner_approved_for_exploratory_evaluation"
        or payload["review_date"] != "2026-11-15"
        or payload["source_sha256"]
        != {
            "utterances": digest(INPUTS["utterance_review"].read_bytes()),
            "fields": digest(INPUTS["field_review"].read_bytes()),
        }
    ):
        raise ValueError("reviewed input provenance differs")
    cases = payload["cases"]
    if (
        type(cases) is not list
        or tuple(case.get("id") for case in cases if type(case) is dict) != CASE_ORDER
    ):
        raise ValueError("reviewed case order differs")
    projected = []
    for case in cases:
        if type(case) is not dict:
            raise ValueError("reviewed case is invalid")
        request = _request_projection(case)
        if (
            type(request["user_message"]) is not str
            or not request["user_message"].strip()
            or type(request["product_index"]) is not int
            or type(request["target_mention"]) is not str
            or not request["target_mention"]
            or type(request["events"]) is not list
        ):
            raise ValueError("reviewed request input is invalid")
        clauses = split_clauses(request["user_message"])
        anchor_span(
            {"clause_index": request["product_index"], "quote": request["target_mention"]},
            clauses,
            field="target",
        )
        for event in request["events"]:
            if (
                type(event["event_index"]) is not int
                or type(event["occurrence"]) is not str
                or event["occurrence"] not in {"observed", "uncertain", "nonoccurring"}
            ):
                raise ValueError("reviewed event input is invalid")
            anchor_span(event["event_span"], clauses, field="event_span")
        projected.append(request)
    actual_calls = tuple(
        f"{case['case_id']}:{event['event_index']}"
        for case in projected
        for event in case["events"]
        if event["occurrence"] != "nonoccurring"
    )
    skipped = tuple(
        f"{case['case_id']}:{event['event_index']}"
        for case in projected
        for event in case["events"]
        if event["occurrence"] == "nonoccurring"
    )
    if actual_calls != CALL_ORDER or skipped != SKIP_ORDER:
        raise ValueError("reviewed event call or skip order differs")
    return projected


def _append(stream, row: dict) -> None:
    encoded = json.dumps(row, ensure_ascii=False, allow_nan=False)
    stream.write(encoded + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def _write_private_raw(path: Path, content: str) -> tuple[str, int]:
    encoded = content.encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        if stat.S_IMODE(os.fstat(stream.fileno()).st_mode) != 0o600:
            raise ValueError("private response permissions differ")
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(encoded), len(encoded)


def _call_event(
    case: dict,
    event: dict,
    policy: RequestPolicy,
    private_dir: Path,
    *,
    completion_call: CompletionCall = post_json_completion,
) -> dict:
    started = time.perf_counter()
    row = {
        "event": "result",
        "case_id": case["case_id"],
        "event_index": event["event_index"],
        "called": True,
        "finish_reason": None,
        "error_code": None,
        "http_status": None,
        "raw_sha256": None,
        "raw_bytes": None,
        "request_latency_ms": None,
    }
    try:
        completion = completion_call(
            event_owner_messages(
                case["user_message"],
                event["event_span"],
                event["occurrence"],
                product_index=case["product_index"],
                target_mention=case["target_mention"],
            ),
            event_owner_schema(case["user_message"]),
            policy=policy,
            endpoint=ENDPOINT,
            model_id=MODEL_ID,
        )
    except TransportError as error:
        row["error_code"] = error.code
        row["http_status"] = error.status_code
    else:
        row["finish_reason"] = completion.finish_reason
        row["raw_sha256"], row["raw_bytes"] = _write_private_raw(
            private_dir / f"{case['case_id']}-event-{event['event_index']}.json.txt",
            completion.content,
        )
        if completion.finish_reason != "stop":
            row["error_code"] = "finish_length"
    row["request_latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return row


def run(
    args: argparse.Namespace,
    *,
    completion_call: CompletionCall = post_json_completion,
) -> None:
    if args.output.exists() or args.private_dir.exists():
        raise FileExistsError("existing or partial run requires manual audit; never overwrite")
    protocol, protocol_sha = load_protocol(args.protocol, args.model_path)
    request_cases = load_request_cases(INPUTS["dataset"])
    v4.verify_container(args.container_name, args.model_path)
    if args.private_dir.is_symlink() or args.private_dir.resolve().is_relative_to(ROOT):
        raise ValueError("raw responses must be outside the repository")
    args.private_dir.mkdir(mode=0o700, parents=False)
    args.private_dir.chmod(0o700)
    if stat.S_IMODE(args.private_dir.stat().st_mode) != 0o700:
        raise ValueError("private response directory permissions differ")
    with args.output.open("x", encoding="utf-8") as stream:
        _append(stream, {"event": "header", "protocol_sha256": protocol_sha})
        policy = RequestPolicy(
            max_tokens=protocol["request_policy"]["max_tokens"],
            temperature=protocol["request_policy"]["temperature"],
            repeat_penalty=protocol["request_policy"]["repeat_penalty"],
            stop=tuple(protocol["request_policy"]["stop"]),
            timeout_seconds=protocol["request_policy"]["timeout_seconds"],
            seed=protocol["request_policy"]["seed"],
        )
        for case in request_cases:
            for event in case["events"]:
                if event["occurrence"] == "nonoccurring":
                    _append(
                        stream,
                        {
                            "event": "result",
                            "case_id": case["case_id"],
                            "event_index": event["event_index"],
                            "called": False,
                            "skip_reason": "nonoccurring",
                            "finish_reason": None,
                            "error_code": None,
                            "http_status": None,
                            "raw_sha256": None,
                            "raw_bytes": None,
                            "request_latency_ms": None,
                        },
                    )
                    continue
                _append(
                    stream,
                    _call_event(
                        case,
                        event,
                        policy,
                        args.private_dir,
                        completion_call=completion_call,
                    ),
                )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--container-name", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--private-dir", required=True, type=Path)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
