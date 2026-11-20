"""Freeze and run a 10-call, local-only ES E→B subject-only probe."""

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
from experiments.as_safety_atomic_edges_v3 import run as v3
from experiments.as_safety_v2.transport import (
    Completion,
    RequestPolicy,
    TransportError,
    post_json_completion,
)
from experiments.as_safety_v4 import run as v4

ROOT = Path(__file__).resolve().parents[2]
INPUTS = {
    **v3.INPUTS,
    "method_v4": ROOT / "docs/portfolio/nlu_safety_atomic_edge_subject_only_v4_method.md",
}
SOURCE_PATHS = v3.SOURCE_PATHS | {
    "experiments/as_safety_atomic_edges_v4/__init__.py",
    "experiments/as_safety_atomic_edges_v4/run.py",
    "experiments/as_safety_atomic_edges_v4/verify.py",
}
KIND = "as_safety_atomic_edge_subject_only_v4_development_v1"
SCOPE = "already_exposed_ai_authored_user_reviewed_es_subject_only_development_probe"
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
CONTAINER_NAME = "as-safety-eb-subject-v4"
REFERENCE_PROTOCOL = (
    ROOT / "evals/structured_nlu/data/ai_heldout/as-safety-eb-format-v3-development-protocol.json"
)
REFERENCE_PROTOCOL_SHA256 = "847dfc8514f39b1d6bcc735c2af651f7123f5a0bba4cbea759687332d8d241be"
REFERENCE_JOURNAL = (
    ROOT
    / "evals/structured_nlu/data/ai_heldout/as-safety-eb-format-v3-development-journal.v1.jsonl"
)
REFERENCE_JOURNAL_SHA256 = "a649b6662135232635057199a949375e5636d6630f3ce492afafcb129c73f366"
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


def _verify_local_docker_endpoint() -> None:
    """Require the inspected container to run on this host's Unix Docker socket."""
    override = os.environ.get("DOCKER_HOST")
    if override is not None and not override.startswith("unix:///"):
        raise ValueError("Docker host must use a local Unix socket")
    context = subprocess.run(
        ("docker", "context", "show"), check=True, capture_output=True, text=True
    ).stdout.strip()
    if not context:
        raise ValueError("Docker context is empty")
    endpoint = subprocess.run(
        ("docker", "context", "inspect", context, "--format", "{{.Endpoints.docker.Host}}"),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not endpoint.startswith("unix:///"):
        raise ValueError("Docker context must use a local Unix socket")
    if override is not None and override != endpoint:
        raise ValueError("Docker host override differs from active context")
    if not Path(endpoint.removeprefix("unix://")).is_socket():
        raise ValueError("local Docker socket is unavailable")


def messages(case: dict, event: dict, condition: str) -> list[dict[str, str]]:
    if condition not in {"baseline", "variant"}:
        raise ValueError("unknown condition")
    original = event_owner_messages(
        case["user_message"],
        event["event_span"],
        event["occurrence"],
        product_index=case["product_index"],
        target_mention=case["target_mention"],
    )
    if condition == "baseline":
        return original
    user = original[1]["content"]
    replacements = {
        "event_subject_evidence_span에는 E와 B를 연결하는 연속 원문 구절을 인용하세요. ": "",
        "implicit이면 앞선 문장의 연결 근거를 인용할 수 있습니다. ": "",
        "주체를 확인할 수 없으면 unresolved와 두 구절 모두 null을 반환하세요. ": (
            "주체를 확인할 수 없으면 unresolved와 subject_span=null을 반환하세요. "
        ),
        "각 구절은 clause_index와 quote를 가진 객체 또는 null입니다. ": (
            "subject_span은 clause_index와 quote를 가진 객체 또는 null입니다. "
        ),
        "JSON 객체 하나에 subject_span, event_subject_kind, "
        "event_subject_evidence_span 세 키만 반환하세요.": (
            "JSON 객체 하나에 subject_span, event_subject_kind 두 키만 반환하세요."
        ),
    }
    for old, new in replacements.items():
        if user.count(old) != 1:
            raise ValueError("source prompt has changed")
        user = user.replace(old, new)
    return [original[0], {"role": "user", "content": user}]


def subject_schema(user_message: str) -> dict:
    schema = event_owner_schema(user_message)
    del schema["properties"]["event_subject_evidence_span"]
    schema["required"].remove("event_subject_evidence_span")
    return schema


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
    if condition not in {"baseline", "variant"}:
        raise ValueError("unknown condition")
    return {"type": "json_object", "schema": schema}


def _historical_hashes() -> dict[str, str]:
    raw = REFERENCE_PROTOCOL.read_bytes()
    if digest(raw) != REFERENCE_PROTOCOL_SHA256:
        raise ValueError("historical protocol digest differs")
    if v1.digest_file(REFERENCE_JOURNAL) != REFERENCE_JOURNAL_SHA256:
        raise ValueError("historical journal digest differs")
    protocol = json.loads(raw, object_pairs_hook=_unique_pairs)
    if protocol.get("kind") != v3.KIND or protocol.get("case_ids") != list(CASE_IDS):
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
        "baseline_response_format": "three_field_schema_constrained_json",
        "variant_response_format": "two_field_schema_constrained_json",
        "historical_v3_protocol_sha256": REFERENCE_PROTOCOL_SHA256,
        "historical_v3_journal_sha256": REFERENCE_JOURNAL_SHA256,
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
        "score_scope": "subject_only_vs_joint_E_to_B; no B_to_A; no safety_route; no official_accuracy",
        "token_usage": "not_collected_by_completion_transport",
    }


def _request_hashes(verified_inputs: dict[str, bytes]) -> dict[str, str]:
    cases = {case["case_id"]: case for case in v1.load_request_cases(verified_inputs)}
    policy = _policy({"request_policy": v1.REQUEST_POLICY})
    hashes = {
        f"{case_id}:{condition}": digest(
            request_bytes(
                messages(cases[case_id], cases[case_id]["events"][0], condition),
                (
                    event_owner_schema(cases[case_id]["user_message"])
                    if condition == "baseline"
                    else subject_schema(cases[case_id]["user_message"])
                ),
                policy,
                condition,
            )
        )
        for case_id, condition in ORDER
    }
    historical = _historical_hashes()
    for case_id in CASE_IDS:
        if hashes[f"{case_id}:baseline"] != historical[f"{case_id}:baseline"]:
            raise ValueError(f"baseline request differs from historical v3: {case_id}")
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
    """Use the same schema-constrained transport for both conditions."""
    if condition not in {"baseline", "variant"}:
        raise ValueError("unknown condition")
    return post_json_completion(
        messages_, schema, policy=policy, endpoint=endpoint, model_id=model_id
    )


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
    if not args.output.parent.is_dir():
        raise ValueError("journal parent directory is unavailable")
    if not os.access(args.output.parent, os.W_OK | os.X_OK):
        raise ValueError("journal parent directory is not writable")
    protocol, protocol_sha, verified = load_protocol(args.protocol, args.model_path)
    if args.container_name != protocol["container_name"]:
        raise ValueError("container name differs")
    cases = {case["case_id"]: case for case in v1.load_request_cases(verified)}
    if any(
        cases[key]["events"][0]["occurrence"] not in {"observed", "uncertain"} for key in CASE_IDS
    ):
        raise ValueError("control event occurrence differs")
    policy = _policy(protocol)
    _verify_local_docker_endpoint()
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
    try:
        journal_stream = args.output.open("x", encoding="utf-8")
    except OSError:
        # No request was made and this run created the empty private directory.
        try:
            args.private_dir.rmdir()
        except OSError:
            pass
        raise
    with journal_stream as stream:
        _append(stream, {"event": "header", "protocol_sha256": protocol_sha})
        for case_id, condition in ORDER:
            case = cases[case_id]
            event = case["events"][0]
            outgoing = messages(case, event, condition)
            schema = (
                event_owner_schema(case["user_message"])
                if condition == "baseline"
                else subject_schema(case["user_message"])
            )
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
