"""Freeze and run a 10-call, local-only ES E→B abstention probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import time
from pathlib import Path

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v1.event_owner import (
    event_owner_messages,
    event_owner_schema,
)
from experiments.as_safety_v2.transport import (
    Completion,
    RequestPolicy,
    TransportError,
    post_json_completion,
)
from experiments.as_safety_v4 import run as v4

ROOT = Path(__file__).resolve().parents[2]
INPUTS = {
    **v1.INPUTS,
    "method_v2": ROOT / "docs/portfolio/nlu_safety_atomic_edge_abstention_v2_method.md",
}
SOURCE_PATHS = v1.SOURCE_PATHS | {
    "experiments/as_safety_atomic_edges_v2/__init__.py",
    "experiments/as_safety_atomic_edges_v2/run.py",
    "experiments/as_safety_atomic_edges_v2/verify.py",
}
KIND = "as_safety_atomic_edge_abstention_v2_development_v1"
SCOPE = "already_exposed_ai_authored_user_reviewed_es_paired_development_probe_only"
CASE_IDS = ("ES01", "ES03", "ES09", "ES17", "ES18")
ORDER = (
    ("ES01", "baseline"),
    ("ES01", "variant"),
    ("ES03", "variant"),
    ("ES03", "baseline"),
    ("ES09", "baseline"),
    ("ES09", "variant"),
    ("ES17", "variant"),
    ("ES17", "baseline"),
    ("ES18", "baseline"),
    ("ES18", "variant"),
)
OLD_SENTENCE = "주체를 확인할 수 없으면 unresolved와 두 구절 모두 null을 반환하세요."
NEW_SENTENCE = (
    "원문에 E와 직접 연결되는 주체·위치 구절이 있으면 해당 구절을 인용하세요. "
    "연결할 구절이 확인되지 않을 때만 unresolved와 두 null을 반환하세요."
)
CONTAINER_NAME = "as-safety-eb-abstention-v2"
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _git(*args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=ROOT, check=True, capture_output=True).stdout


def _committed(commit: str, relative: str) -> bytes:
    if not COMMIT_RE.fullmatch(commit) or relative.startswith("/") or ".." in Path(relative).parts:
        raise ValueError("invalid committed reference")
    return _git("show", f"{commit}:{relative}")


def _clean_checkout() -> None:
    if _git("status", "--porcelain").strip():
        raise ValueError("checkout must be clean before preparing or running")


def messages(case: dict, event: dict, condition: str) -> list[dict[str, str]]:
    if condition not in {"baseline", "variant"}:
        raise ValueError("unknown condition")
    result = event_owner_messages(
        case["user_message"],
        event["event_span"],
        event["occurrence"],
        product_index=case["product_index"],
        target_mention=case["target_mention"],
    )
    original = result[1]["content"]
    if original.count(OLD_SENTENCE) != 1:
        raise ValueError("original abstention sentence differs")
    if condition == "variant":
        result[1]["content"] = original.replace(OLD_SENTENCE, NEW_SENTENCE)
    return result


def request_bytes(messages_: list[dict[str, str]], schema: dict, policy: RequestPolicy) -> bytes:
    """Match the transport's exact UTF-8 JSON body, not merely a normalized projection."""
    payload = {
        "model": v1.MODEL_ID,
        "messages": messages_,
        "max_tokens": policy.max_tokens,
        "temperature": policy.temperature,
        "repeat_penalty": policy.repeat_penalty,
        "stop": list(policy.stop),
        "seed": policy.seed,
        "response_format": {"type": "json_object", "schema": schema},
    }
    return json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")


def _identity() -> dict:
    return {
        "kind": KIND,
        "claim_scope": SCOPE,
        "case_ids": list(CASE_IDS),
        "call_order": [list(pair) for pair in ORDER],
        "baseline_sentence_sha256": digest(OLD_SENTENCE.encode()),
        "variant_sentence_sha256": digest(NEW_SENTENCE.encode()),
        "model_sha256": v1.MODEL_SHA,
        "server_image_digest": v1.IMAGE,
        "container_name": CONTAINER_NAME,
        "endpoint": v1.ENDPOINT,
        "model_id": v1.MODEL_ID,
        "server_args": list(v1.SERVER_ARGS),
        "local_runtime": v1.RUNTIME,
        "request_policy": v1.REQUEST_POLICY,
        "retry_policy": v1.RETRY_POLICY,
        "private_output": v1.PRIVATE_OUTPUT,
        "score_scope": "E_to_B_only; no B_to_A; no safety_route; no official_accuracy",
    }


def _request_hashes(verified_inputs: dict[str, bytes]) -> dict[str, str]:
    cases = {case["case_id"]: case for case in v1.load_request_cases(verified_inputs)}
    policy = _policy({"request_policy": v1.REQUEST_POLICY})
    return {
        f"{case_id}:{condition}": digest(
            request_bytes(
                messages(cases[case_id], cases[case_id]["events"][0], condition),
                event_owner_schema(cases[case_id]["user_message"]),
                policy,
            )
        )
        for case_id, condition in ORDER
    }


def prepare_protocol(path: Path, model_path: Path) -> dict:
    if path.exists():
        raise FileExistsError("protocol already exists")
    _clean_checkout()
    commit = _git("rev-parse", "HEAD").decode().strip()
    if not model_path.is_file() or v1.digest_file(model_path) != v1.MODEL_SHA:
        raise ValueError("model file digest differs")
    sources = {}
    for relative in sorted(SOURCE_PATHS):
        current = (ROOT / relative).read_bytes()
        if current != _committed(commit, relative):
            raise ValueError(f"source differs from commit: {relative}")
        sources[relative] = digest(current)
    inputs = {}
    verified_inputs = {}
    for key, source in INPUTS.items():
        relative = source.relative_to(ROOT).as_posix()
        current = source.read_bytes()
        if current != _committed(commit, relative):
            raise ValueError(f"input differs from commit: {key}")
        inputs[key] = digest(current)
        verified_inputs[key] = current
    protocol = {
        **_identity(),
        "frozen_code_commit": commit,
        "source_manifest": sources,
        "input_hashes": inputs,
        "request_sha256_by_call": _request_hashes(verified_inputs),
    }
    with path.open("x", encoding="utf-8") as stream:
        json.dump(protocol, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    return protocol


def load_protocol(path: Path, model_path: Path) -> tuple[dict, str, dict[str, bytes]]:
    raw = path.read_bytes()
    protocol = json.loads(raw)
    expected = _identity()
    if (
        type(protocol) is not dict
        or set(protocol)
        != set(expected)
        | {"frozen_code_commit", "source_manifest", "input_hashes", "request_sha256_by_call"}
        or any(protocol.get(key) != value for key, value in expected.items())
    ):
        raise ValueError("protocol identity differs")
    commit = protocol["frozen_code_commit"]
    if type(commit) is not str or not COMMIT_RE.fullmatch(commit):
        raise ValueError("frozen commit differs")
    if not model_path.is_file() or v1.digest_file(model_path) != v1.MODEL_SHA:
        raise ValueError("model file digest differs")
    if (
        type(protocol["source_manifest"]) is not dict
        or set(protocol["source_manifest"]) != SOURCE_PATHS
    ):
        raise ValueError("source manifest differs")
    for relative, expected_sha in protocol["source_manifest"].items():
        frozen = _committed(commit, relative)
        if (
            type(expected_sha) is not str
            or not SHA_RE.fullmatch(expected_sha)
            or digest(frozen) != expected_sha
            or (ROOT / relative).read_bytes() != frozen
        ):
            raise ValueError(f"frozen source differs: {relative}")
    if type(protocol["input_hashes"]) is not dict or set(protocol["input_hashes"]) != set(INPUTS):
        raise ValueError("input manifest differs")
    verified = {}
    for key, source in INPUTS.items():
        frozen = _committed(commit, source.relative_to(ROOT).as_posix())
        expected_sha = protocol["input_hashes"][key]
        current = source.read_bytes()
        if (
            type(expected_sha) is not str
            or not SHA_RE.fullmatch(expected_sha)
            or digest(frozen) != expected_sha
            or current != frozen
        ):
            raise ValueError(f"frozen input differs: {key}")
        verified[key] = current
    if protocol["request_sha256_by_call"] != _request_hashes(verified):
        raise ValueError("frozen request hashes differ")
    if _git("show", f"HEAD:{path.resolve().relative_to(ROOT).as_posix()}") != raw:
        raise ValueError("protocol must be committed before model calls")
    _clean_checkout()
    return protocol, digest(raw), verified


def _policy(protocol: dict) -> RequestPolicy:
    request = protocol["request_policy"]
    return RequestPolicy(
        max_tokens=request["max_tokens"],
        temperature=request["temperature"],
        repeat_penalty=request["repeat_penalty"],
        stop=tuple(request["stop"]),
        timeout_seconds=request["timeout_seconds"],
        seed=request["seed"],
    )


def _append(stream, row: dict) -> None:
    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def run(args: argparse.Namespace, *, completion_call=post_json_completion) -> None:
    if args.output.exists() or args.private_dir.exists():
        raise FileExistsError("partial or existing run requires manual audit")
    protocol, protocol_sha, verified = load_protocol(args.protocol, args.model_path)
    if args.container_name != protocol["container_name"]:
        raise ValueError("container name differs")
    cases = {case["case_id"]: case for case in v1.load_request_cases(verified)}
    if any(
        cases[key]["events"][0]["occurrence"] not in {"observed", "uncertain"} for key in CASE_IDS
    ):
        raise ValueError("control event occurrence differs")
    v4.verify_container(args.container_name, args.model_path)
    if args.private_dir.is_symlink() or args.private_dir.resolve().is_relative_to(ROOT):
        raise ValueError("private output must be outside repository")
    args.private_dir.mkdir(mode=0o700, parents=False)
    args.private_dir.chmod(0o700)
    if stat.S_IMODE(args.private_dir.stat().st_mode) != 0o700:
        raise ValueError("private output permissions differ")
    policy = _policy(protocol)
    with args.output.open("x", encoding="utf-8") as stream:
        _append(stream, {"event": "header", "protocol_sha256": protocol_sha})
        for case_id, condition in ORDER:
            case = cases[case_id]
            event = case["events"][0]
            outgoing = messages(case, event, condition)
            schema = event_owner_schema(case["user_message"])
            request_sha = digest(request_bytes(outgoing, schema, policy))
            if request_sha != protocol["request_sha256_by_call"][f"{case_id}:{condition}"]:
                raise ValueError("outgoing request differs from frozen protocol")
            row = {
                "event": "result",
                "case_id": case_id,
                "event_index": 1,
                "condition": condition,
                "request_sha256": request_sha,
                "finish_reason": None,
                "error_code": None,
                "http_status": None,
                "raw_sha256": None,
                "raw_bytes": None,
                "request_latency_ms": None,
            }
            started = time.perf_counter()
            try:
                completion: Completion = completion_call(
                    outgoing, schema, policy=policy, endpoint=v1.ENDPOINT, model_id=v1.MODEL_ID
                )
            except TransportError as error:
                row["request_latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
                row["error_code"], row["http_status"] = error.code, error.status_code
            else:
                row["request_latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
                row["finish_reason"] = completion.finish_reason
                row["raw_sha256"], row["raw_bytes"] = v1._write_private_raw(
                    args.private_dir / f"{case_id}-{condition}.json.txt", completion.content
                )
                if completion.finish_reason != "stop":
                    row["error_code"] = "finish_length"
            _append(stream, row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "run"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--protocol", type=Path, required=True)
        sub.add_argument("--model-path", type=Path, required=True)
        if command == "run":
            sub.add_argument("--container-name", required=True)
            sub.add_argument("--output", type=Path, required=True)
            sub.add_argument("--private-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare_protocol(args.protocol, args.model_path)
    else:
        run(args)


if __name__ == "__main__":
    main()
