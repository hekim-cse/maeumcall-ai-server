"""Freeze and run a 10-call, local-only ES E→B response-format probe."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import stat
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v1.event_owner import (
    event_owner_messages,
    event_owner_schema,
)
from experiments.as_safety_atomic_edges_v2 import run as v2
from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.transport import (
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    Completion,
    RequestPolicy,
    TransportError,
    _NoRedirect,
    post_json_completion,
)
from experiments.as_safety_v4 import run as v4

ROOT = Path(__file__).resolve().parents[2]
INPUTS = {
    **v1.INPUTS,
    "method_v2": ROOT / "docs/portfolio/nlu_safety_atomic_edge_abstention_v2_method.md",
    "method_v3": ROOT / "docs/portfolio/nlu_safety_atomic_edge_format_v3_method.md",
}
SOURCE_PATHS = v2.SOURCE_PATHS | {
    "experiments/as_safety_atomic_edges_v3/__init__.py",
    "experiments/as_safety_atomic_edges_v3/run.py",
    "experiments/as_safety_atomic_edges_v3/verify.py",
}
KIND = "as_safety_atomic_edge_response_format_v3_development_v1"
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
CONTAINER_NAME = "as-safety-eb-format-v3"
REFERENCE_PROTOCOL = (
    ROOT
    / "evals/structured_nlu/data/ai_heldout/as-safety-eb-abstention-v2-development-protocol.json"
)
REFERENCE_PROTOCOL_SHA256 = "fa7a2f574220e7fb92275277895d5aa14c14f12434cf715c7fdb8aa8702de56c"
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


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate protocol JSON key")
        result[key] = value
    return result


def _container_identity(name: str) -> tuple[str, str]:
    """Detect a restarted or replaced model server across sequential calls."""
    observed = json.loads(
        subprocess.run(
            ("docker", "inspect", name), check=True, capture_output=True, text=True
        ).stdout
    )[0]
    container_id = observed.get("Id")
    state = observed.get("State")
    started_at = state.get("StartedAt") if type(state) is dict else None
    if (
        type(container_id) is not str
        or not container_id
        or type(started_at) is not str
        or not started_at
        or state.get("Running") is not True
    ):
        raise ValueError("model server identity differs")
    return container_id, started_at


def messages(case: dict, event: dict, condition: str) -> list[dict[str, str]]:
    if condition not in {"baseline", "variant"}:
        raise ValueError("unknown condition")
    return event_owner_messages(
        case["user_message"],
        event["event_span"],
        event["occurrence"],
        product_index=case["product_index"],
        target_mention=case["target_mention"],
    )


def request_bytes(
    messages_: list[dict[str, str]], schema: dict, policy: RequestPolicy, condition: str
) -> bytes:
    """Match the transport's exact UTF-8 JSON body, not merely a normalized projection."""
    payload = {
        "model": v1.MODEL_ID,
        "messages": messages_,
        "max_tokens": policy.max_tokens,
        "temperature": policy.temperature,
        "repeat_penalty": policy.repeat_penalty,
        "stop": list(policy.stop),
        "seed": policy.seed,
        "response_format": response_format(schema, condition),
    }
    return json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")


def response_format(schema: dict, condition: str) -> dict:
    if condition == "baseline":
        return {"type": "json_object", "schema": schema}
    if condition == "variant":
        return {"type": "json_object"}
    raise ValueError("unknown condition")


def _historical_hashes() -> dict[str, str]:
    raw = REFERENCE_PROTOCOL.read_bytes()
    if digest(raw) != REFERENCE_PROTOCOL_SHA256:
        raise ValueError("historical protocol digest differs")
    protocol = json.loads(raw, object_pairs_hook=_unique_pairs)
    if protocol.get("kind") != v2.KIND or protocol.get("case_ids") != list(CASE_IDS):
        raise ValueError("historical protocol identity differs")
    hashes = protocol.get("request_sha256_by_call")
    if type(hashes) is not dict:
        raise ValueError("historical request manifest differs")
    return hashes


def _identity() -> dict:
    return {
        "kind": KIND,
        "claim_scope": SCOPE,
        "case_ids": list(CASE_IDS),
        "call_order": [list(pair) for pair in ORDER],
        "baseline_response_format": "json_object_with_schema",
        "variant_response_format": "plain_json_object",
        "historical_v2_protocol_sha256": REFERENCE_PROTOCOL_SHA256,
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
    hashes = {
        f"{case_id}:{condition}": digest(
            request_bytes(
                messages(cases[case_id], cases[case_id]["events"][0], condition),
                event_owner_schema(cases[case_id]["user_message"]),
                policy,
                condition,
            )
        )
        for case_id, condition in ORDER
    }
    historical = _historical_hashes()
    for case_id in CASE_IDS:
        if hashes[f"{case_id}:baseline"] != historical[f"{case_id}:baseline"]:
            raise ValueError(f"baseline request differs from historical v2: {case_id}")
    return hashes


def post_format_completion(
    messages_: list[dict[str, str]],
    schema: dict,
    *,
    condition: str,
    policy: RequestPolicy,
    endpoint: str,
    model_id: str,
) -> Completion:
    """Use the unchanged transport for baseline and an equivalent plain-JSON path."""
    if condition == "baseline":
        return post_json_completion(
            messages_, schema, policy=policy, endpoint=endpoint, model_id=model_id
        )
    if condition != "variant" or endpoint != v1.ENDPOINT or model_id != v1.MODEL_ID:
        raise ValueError("request identity differs")
    if (
        type(messages_) is not list
        or not messages_
        or any(
            type(message) is not dict
            or set(message) != {"role", "content"}
            or type(message["role"]) is not str
            or message["role"] not in {"system", "user", "assistant"}
            or type(message["content"]) is not str
            for message in messages_
        )
        or type(schema) is not dict
        or type(policy) is not RequestPolicy
    ):
        raise ValueError("request messages, schema or policy differ")
    encoded = request_bytes(messages_, schema, policy, condition)
    if len(encoded) > MAX_REQUEST_BYTES:
        raise TransportError("request_too_large")
    request = urllib.request.Request(
        endpoint, data=encoded, headers={"Content-Type": "application/json"}, method="POST"
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=policy.timeout_seconds) as response:
            if response.status != 200:
                raise TransportError("http_status", response.status)
            raw_body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        raise TransportError("http_error", error.code) from None
    except urllib.error.URLError:
        raise TransportError("network_error") from None
    except TimeoutError:
        raise TransportError("timeout") from None
    except (http.client.HTTPException, OSError):
        raise TransportError("network_error") from None
    if type(raw_body) is not bytes or len(raw_body) > MAX_RESPONSE_BYTES:
        raise TransportError("response_too_large")
    try:
        body = parse_model_json(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, ValidationError):
        raise TransportError("invalid_response_json") from None
    if type(body) is not dict or type(body.get("choices")) is not list or not body["choices"]:
        raise TransportError("response_fields_invalid")
    choice = body["choices"][0]
    if type(choice) is not dict or type(choice.get("message")) is not dict:
        raise TransportError("response_fields_invalid")
    content = choice["message"].get("content")
    finish = choice.get("finish_reason")
    if (
        type(content) is not str
        or not content.strip()
        or type(finish) is not str
        or finish not in {"stop", "length"}
    ):
        raise TransportError("response_fields_invalid")
    return Completion(content=content, finish_reason=finish)


def prepare_protocol(path: Path, model_path: Path) -> dict:
    if not path.resolve().is_relative_to(ROOT):
        raise ValueError("protocol must be created inside repository")
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
    protocol = json.loads(raw, object_pairs_hook=_unique_pairs)
    expected = _identity()
    if (
        type(protocol) is not dict
        or set(protocol)
        != set(expected)
        | {"frozen_code_commit", "source_manifest", "input_hashes", "request_sha256_by_call"}
        or any(protocol.get(key) != value for key, value in expected.items())
    ):
        raise ValueError("protocol identity differs")
    if (
        type(protocol["request_policy"]) is not dict
        or type(protocol["request_policy"].get("timeout_seconds")) is not int
    ):
        raise ValueError("request timeout type differs")
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


def run(args: argparse.Namespace, *, completion_call=post_format_completion) -> None:
    if args.output.exists() or args.private_dir.exists():
        raise FileExistsError("partial or existing run requires manual audit")
    if args.output.resolve().is_relative_to(args.private_dir.resolve()):
        raise ValueError("journal must be outside private response directory")
    protocol, protocol_sha, verified = load_protocol(args.protocol, args.model_path)
    if args.container_name != protocol["container_name"]:
        raise ValueError("container name differs")
    cases = {case["case_id"]: case for case in v1.load_request_cases(verified)}
    if any(
        cases[key]["events"][0]["occurrence"] not in {"observed", "uncertain"} for key in CASE_IDS
    ):
        raise ValueError("control event occurrence differs")
    policy = _policy(protocol)
    initial_identity = _container_identity(args.container_name)
    v4.verify_container(args.container_name, args.model_path)
    if _container_identity(args.container_name) != initial_identity:
        raise ValueError("model server changed during configuration check")
    if args.private_dir.is_symlink() or args.private_dir.resolve().is_relative_to(ROOT):
        raise ValueError("private output must be outside repository")
    args.private_dir.mkdir(mode=0o700, parents=False)
    args.private_dir.chmod(0o700)
    if stat.S_IMODE(args.private_dir.stat().st_mode) != 0o700:
        raise ValueError("private output permissions differ")
    with args.output.open("x", encoding="utf-8") as stream:
        _append(stream, {"event": "header", "protocol_sha256": protocol_sha})
        for case_id, condition in ORDER:
            case = cases[case_id]
            event = case["events"][0]
            outgoing = messages(case, event, condition)
            schema = event_owner_schema(case["user_message"])
            request_sha = digest(request_bytes(outgoing, schema, policy, condition))
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
            if _container_identity(args.container_name) != initial_identity:
                raise ValueError("model server changed before request; partial run requires audit")
            started = time.perf_counter()
            try:
                completion: Completion = completion_call(
                    outgoing,
                    schema,
                    condition=condition,
                    policy=policy,
                    endpoint=v1.ENDPOINT,
                    model_id=v1.MODEL_ID,
                )
            except TransportError as error:
                row["request_latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
                row["error_code"], row["http_status"] = error.code, error.status_code
            else:
                row["request_latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
                try:
                    completion.content.encode("utf-8")
                except UnicodeEncodeError:
                    row["error_code"] = "response_fields_invalid"
                else:
                    row["finish_reason"] = completion.finish_reason
                    row["raw_sha256"], row["raw_bytes"] = v1._write_private_raw(
                        args.private_dir / f"{case_id}-{condition}.json.txt", completion.content
                    )
                    if completion.finish_reason != "stop":
                        row["error_code"] = "finish_length"
            if _container_identity(args.container_name) != initial_identity:
                raise ValueError("model server changed during run; partial run requires audit")
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
