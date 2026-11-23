"""Freeze and run the one remaining artificial system-instruction control."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import time
from pathlib import Path

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v4 import run as v4
from experiments.as_safety_atomic_edges_v5 import run as v5
from experiments.as_safety_atomic_edges_v7 import run as v7
from experiments.as_safety_atomic_edges_v10.model_attestation import guarded_call
from experiments.as_safety_atomic_edges_v12 import pair_contract
from experiments.as_safety_atomic_edges_v12 import run as v12
from experiments.as_safety_atomic_edges_v14 import run as v14
from experiments.as_safety_atomic_edges_v14 import verify as v14_verify
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.transport import TransportError

ROOT = v12.ROOT
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
PROTOCOL = DATA / "as-safety-system-control-v15-protocol.json"
JOURNAL = DATA / "as-safety-system-control-v15-journal.v1.jsonl"
PRIVATE_DIR = Path("/private/tmp/as-safety-system-control-v15-raw")
CALL = "system_forced_unsupported"
KIND = "as_safety_system_control_v15_development_v1"
V14_PROTOCOL_SHA = "389f54d5efdde788bc95d4b5b7b2b96474363b15fa8a38d9fd05af34c4b57001"
V14_JOURNAL_SHA = "9b56ed175df2f8acfdbcc518ea2f47a78c11ce081a0d6590e5661acd8fadd020"
SOURCES = tuple(
    sorted(
        set(v14.SOURCES)
        | {
            "docs/portfolio/nlu_safety_system_control_v15_method.md",
            "experiments/as_safety_atomic_edges_v15/__init__.py",
            "experiments/as_safety_atomic_edges_v15/run.py",
            "experiments/as_safety_atomic_edges_v15/verify.py",
            "tests/test_as_safety_system_control_v15.py",
        }
    )
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _prior_guard() -> None:
    if _sha(v14.PROTOCOL.read_bytes()) != V14_PROTOCOL_SHA:
        raise ValueError("v14 protocol differs")
    if _sha(v14.JOURNAL.read_bytes()) != V14_JOURNAL_SHA:
        raise ValueError("v14 journal differs")
    prior = v14_verify.verify()
    if (
        prior["calls_completed"] != 1
        or prior["schema_enum_observed"] is not True
        or prior["per_call"][0]["error_code"] != "evidence_clause_missing"
        or prior["explicit_instruction_followed"] is not None
    ):
        raise ValueError("v14 partial result differs")


def _request(policy) -> bytes:
    messages, schema = v14._messages_schema(CALL)
    return v4.request_bytes(messages, schema, policy, "variant")


def prepare(model_path: Path) -> None:
    if PROTOCOL.exists() or JOURNAL.exists() or PRIVATE_DIR.exists():
        raise FileExistsError("existing or partial control requires manual audit")
    v12._clean()
    _prior_guard()
    commit = v12._git("rev-parse", "HEAD").decode().strip()
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    request = _request(policy)
    with v12.v10_run._server(model_path) as attestor:
        tokens = guarded_call(attestor, lambda: v7._tokenize_request(request))
    if tokens + policy.max_tokens >= v1.RUNTIME["context_tokens"]:
        raise ValueError("request exceeds context")
    sources = {path: _sha(v12._git("show", f"{commit}:{path}")) for path in SOURCES}
    if sources != {path: _sha((ROOT / path).read_bytes()) for path in SOURCES}:
        raise ValueError("source differs from committed code")
    payload = {
        "kind": KIND,
        "scope": "one_artificial_exposed_system_prompt_control_no_semantic_accuracy",
        "call": CALL,
        "frozen_code_commit": commit,
        "source_sha256": sources,
        "cases_sha256": _sha(v5.DATA.read_bytes()),
        "v14_protocol_sha256": V14_PROTOCOL_SHA,
        "v14_journal_sha256": V14_JOURNAL_SHA,
        "prompt_canary_sha256": _sha(v14.PROMPT_CANARY.encode("utf-8")),
        "model_sha256": v1.MODEL_SHA,
        "image_digest": v1.IMAGE,
        "container_name": v12.v10_run.CONTAINER,
        "server_args": list(v1.SERVER_ARGS),
        "request_policy": v1.REQUEST_POLICY,
        "retry_policy": v1.RETRY_POLICY,
        "request_sha256": _sha(request),
        "input_tokens": tokens,
        "max_context_tokens": v1.RUNTIME["context_tokens"],
        "journal": JOURNAL.relative_to(ROOT).as_posix(),
        "private_output": "outside_repository_mode_0700_files_0600",
    }
    with PROTOCOL.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def _load_protocol() -> tuple[dict, str, object, bytes]:
    raw = PROTOCOL.read_bytes()
    protocol = json.loads(raw, object_pairs_hook=v4._unique_pairs)
    expected = {
        "kind",
        "scope",
        "call",
        "frozen_code_commit",
        "source_sha256",
        "cases_sha256",
        "v14_protocol_sha256",
        "v14_journal_sha256",
        "prompt_canary_sha256",
        "model_sha256",
        "image_digest",
        "container_name",
        "server_args",
        "request_policy",
        "retry_policy",
        "request_sha256",
        "input_tokens",
        "max_context_tokens",
        "journal",
        "private_output",
    }
    if (
        type(protocol) is not dict
        or set(protocol) != expected
        or protocol["kind"] != KIND
        or protocol["scope"] != "one_artificial_exposed_system_prompt_control_no_semantic_accuracy"
        or protocol["call"] != CALL
        or set(protocol["source_sha256"]) != set(SOURCES)
        or protocol["v14_protocol_sha256"] != V14_PROTOCOL_SHA
        or protocol["v14_journal_sha256"] != V14_JOURNAL_SHA
        or protocol["prompt_canary_sha256"] != _sha(v14.PROMPT_CANARY.encode("utf-8"))
        or protocol["model_sha256"] != v1.MODEL_SHA
        or protocol["image_digest"] != v1.IMAGE
        or protocol["container_name"] != v12.v10_run.CONTAINER
        or protocol["server_args"] != list(v1.SERVER_ARGS)
        or protocol["request_policy"] != v1.REQUEST_POLICY
        or protocol["retry_policy"] != v1.RETRY_POLICY
        or protocol["max_context_tokens"] != v1.RUNTIME["context_tokens"]
        or protocol["journal"] != JOURNAL.relative_to(ROOT).as_posix()
        or protocol["private_output"] != "outside_repository_mode_0700_files_0600"
    ):
        raise ValueError("protocol identity differs")
    _prior_guard()
    commit = protocol["frozen_code_commit"]
    for path, digest in protocol["source_sha256"].items():
        if digest != _sha(v12._git("show", f"{commit}:{path}")) or digest != _sha(
            (ROOT / path).read_bytes()
        ):
            raise ValueError("frozen source differs")
    if protocol["cases_sha256"] != _sha(v5.DATA.read_bytes()):
        raise ValueError("case source differs")
    policy = v5._policy(protocol)
    request = _request(policy)
    if protocol["request_sha256"] != _sha(request):
        raise ValueError("frozen request differs")
    if (
        type(protocol["input_tokens"]) is not int
        or protocol["input_tokens"] <= 0
        or protocol["input_tokens"] + policy.max_tokens >= v1.RUNTIME["context_tokens"]
    ):
        raise ValueError("frozen token budget differs")
    if v12._git("show", f"HEAD:{PROTOCOL.relative_to(ROOT).as_posix()}") != raw:
        raise ValueError("protocol must be committed before calls")
    v12._clean()
    return protocol, _sha(raw), policy, request


def run(model_path: Path) -> None:
    if JOURNAL.exists() or PRIVATE_DIR.exists():
        raise FileExistsError("existing or partial control requires manual audit")
    protocol, protocol_sha, policy, request = _load_protocol()
    with v12.v10_run._server(model_path) as attestor:
        count = guarded_call(attestor, lambda: v7._tokenize_request(request))
        if count != protocol["input_tokens"]:
            raise ValueError("tokenizer count differs")
        PRIVATE_DIR.mkdir(mode=0o700)
        if stat.S_IMODE(PRIVATE_DIR.stat().st_mode) != 0o700:
            raise ValueError("private directory mode differs")
        with JOURNAL.open("x", encoding="utf-8") as stream:
            v5._append(stream, {"event": "header", "protocol_sha256": protocol_sha})
            row = {
                "event": "result",
                "call": CALL,
                "request_sha256": _sha(request),
                "finish_reason": None,
                "error_code": None,
                "http_status": None,
                "raw_sha256": None,
                "raw_bytes": None,
                "request_latency_ms": None,
            }
            messages, schema = v14._messages_schema(CALL)
            started = time.perf_counter()
            try:
                completion = guarded_call(
                    attestor,
                    lambda: v4.post_format_completion(
                        messages,
                        schema,
                        condition="variant",
                        policy=policy,
                        endpoint=v1.ENDPOINT,
                        model_id=v1.MODEL_ID,
                    ),
                )
            except TransportError as error:
                row["error_code"], row["http_status"] = error.code, error.status_code
            else:
                row["finish_reason"] = completion.finish_reason
                row["raw_sha256"], row["raw_bytes"] = v1._write_private_raw(
                    PRIVATE_DIR / f"{CALL}.json.txt", completion.content
                )
                if completion.finish_reason != "stop":
                    row["error_code"] = "finish_length"
                else:
                    try:
                        pair_contract.validate_response(completion.content, v14._pair())
                    except ValidationError as error:
                        row["error_code"] = error.code
            row["request_latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
            v5._append(stream, row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("--model-path", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.model_path)
    else:
        run(args.model_path)


if __name__ == "__main__":
    main()
