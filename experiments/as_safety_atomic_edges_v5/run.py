"""Freeze and run two local-only E→B control calls, without retries."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import time
from datetime import date
from pathlib import Path

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v1 import verify as v1_verify
from experiments.as_safety_atomic_edges_v4 import run as v4
from experiments.as_safety_v2.transport import RequestPolicy, TransportError
from experiments.as_safety_v4 import run as server

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout/as-safety-eb-controls-v5-cases.json"
METHOD = ROOT / "docs/portfolio/nlu_safety_atomic_edge_controls_v5_method.md"
INPUTS = {"control_cases": DATA, "method": METHOD}
SOURCE_PATHS = v4.SOURCE_PATHS | {
    "experiments/as_safety_atomic_edges_v5/__init__.py",
    "experiments/as_safety_atomic_edges_v5/run.py",
    "experiments/as_safety_atomic_edges_v5/verify.py",
    "tests/test_as_safety_atomic_edge_controls_v5.py",
}
KIND = "as_safety_eb_controls_v5_development_v1"
SCOPE = "ai_authored_user_reviewed_development_controls_only"
CASE_IDS = ("PC01", "NC01")
ORDER = CASE_IDS
CONTAINER_NAME = "as-safety-eb-controls-v5"
JOURNAL = (
    ROOT
    / "evals/structured_nlu/data/ai_heldout/as-safety-eb-controls-v5-development-journal.v1.jsonl"
)
PRIVATE_DIR = Path("/private/tmp/as-safety-eb-controls-v5-raw")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
CASE_FIELDS = {
    "case_id",
    "user_message",
    "product_index",
    "target_mention",
    "event_span",
    "occurrence",
    "gold_subject_span",
    "gold_kind",
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_cases(raw: bytes) -> dict[str, dict]:
    """Require approved labels but never pass either gold field to the model."""
    payload = json.loads(raw, object_pairs_hook=v4._unique_pairs)
    if (
        type(payload) is not dict
        or set(payload) != {"kind", "provenance", "review_status", "review_date", "cases"}
        or payload["kind"] != "as_safety_eb_controls_v5_cases_v1"
        or payload["provenance"] != "ai_authored_development_control"
        or payload["review_status"] != "user_approved_for_development_probe"
        or type(payload["review_date"]) is not str
        or not DATE_RE.fullmatch(payload["review_date"])
        or type(payload["cases"]) is not list
        or len(payload["cases"]) != len(CASE_IDS)
    ):
        raise ValueError("control cases need recorded user review")
    try:
        date.fromisoformat(payload["review_date"])
    except ValueError as error:
        raise ValueError("review date invalid") from error
    cases = {}
    for index, case in enumerate(payload["cases"]):
        if type(case) is not dict or set(case) != CASE_FIELDS or case["case_id"] != CASE_IDS[index]:
            raise ValueError("control case identity differs")
        if (
            type(case["user_message"]) is not str
            or not case["user_message"].strip()
            or type(case["product_index"]) is not int
            or type(case["target_mention"]) is not str
            or not case["target_mention"].strip()
            or case["occurrence"] != "observed"
        ):
            raise ValueError("control source fields invalid")
        clauses = v1_verify._clauses(case["user_message"])
        try:
            if v1_verify._span(case["event_span"], clauses) is None:
                raise ValueError("event span is empty")
            if (
                v1_verify._span(
                    {"clause_index": case["product_index"], "quote": case["target_mention"]},
                    clauses,
                )
                is None
            ):
                raise ValueError("target span is empty")
        except v1_verify.VerificationError as error:
            raise ValueError("control source span invalid") from error
        if case["case_id"] == "PC01":
            if case["gold_kind"] != "location" or case["gold_subject_span"] is None:
                raise ValueError("positive control label differs")
            try:
                v1_verify._span(case["gold_subject_span"], clauses)
            except v1_verify.VerificationError as error:
                raise ValueError("positive control label invalid") from error
        elif case["gold_kind"] != "unresolved" or case["gold_subject_span"] is not None:
            raise ValueError("negative control label differs")
        # v4's request builder also validates the reviewed target and event spans.
        _outgoing(case)
        cases[case["case_id"]] = case
    return cases


def _outgoing(case: dict) -> list[dict[str, str]]:
    event = {"event_span": case["event_span"], "occurrence": case["occurrence"]}
    return v4.messages(case, event, "variant")


def _schema(case: dict) -> dict:
    return v4.subject_schema(case["user_message"])


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


def _request_sha(case: dict, policy: RequestPolicy) -> str:
    return digest(v4.request_bytes(_outgoing(case), _schema(case), policy, "variant"))


def _identity() -> dict:
    return {
        "kind": KIND,
        "claim_scope": SCOPE,
        "case_ids": list(CASE_IDS),
        "call_order": list(ORDER),
        "response_format": "v4_subject_only_two_field_schema_constrained_json",
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
        "score_scope": "two development controls; no B_to_A; no safety route; no official accuracy",
        "token_usage": "not_collected_by_completion_transport",
    }


def _committed(commit: str, relative: str) -> bytes:
    if type(commit) is not str or not COMMIT_RE.fullmatch(commit):
        raise ValueError("frozen commit invalid")
    if relative.startswith("/") or ".." in Path(relative).parts:
        raise ValueError("frozen path invalid")
    return v4._committed(commit, relative)


def _manifest(commit: str, paths: dict[str, Path] | set[str]) -> dict[str, str]:
    manifest = {}
    for key in sorted(paths):
        path = paths[key] if isinstance(paths, dict) else ROOT / key
        frozen = _committed(commit, path.relative_to(ROOT).as_posix())
        current = path.read_bytes()
        if current != frozen:
            raise ValueError(f"frozen file differs: {key}")
        manifest[key] = digest(current)
    return manifest


def prepare_protocol(path: Path, model_path: Path) -> dict:
    if not path.resolve().is_relative_to(ROOT):
        raise ValueError("protocol must be inside repository")
    if path.exists():
        raise FileExistsError("protocol already exists")
    v4._clean_checkout()
    commit = v4._git("rev-parse", "HEAD").decode().strip()
    if not model_path.is_file() or v1.digest_file(model_path) != v1.MODEL_SHA:
        raise ValueError("model file digest differs")
    source_manifest = _manifest(commit, SOURCE_PATHS)
    input_hashes = _manifest(commit, INPUTS)
    cases = _load_cases(DATA.read_bytes())
    policy = _policy({"request_policy": v1.REQUEST_POLICY})
    protocol = {
        **_identity(),
        "frozen_code_commit": commit,
        "source_manifest": source_manifest,
        "input_hashes": input_hashes,
        "request_sha256_by_call": {key: _request_sha(cases[key], policy) for key in ORDER},
    }
    with path.open("x", encoding="utf-8") as stream:
        json.dump(protocol, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    return protocol


def load_protocol(path: Path, model_path: Path) -> tuple[dict, str, dict[str, dict]]:
    raw = path.read_bytes()
    protocol = json.loads(raw, object_pairs_hook=v4._unique_pairs)
    expected = _identity()
    if (
        type(protocol) is not dict
        or set(protocol)
        != set(expected)
        | {
            "frozen_code_commit",
            "source_manifest",
            "input_hashes",
            "request_sha256_by_call",
        }
        or any(protocol.get(key) != value for key, value in expected.items())
        or type(protocol["request_policy"]) is not dict
        or type(protocol["request_policy"].get("timeout_seconds")) is not int
    ):
        raise ValueError("protocol identity differs")
    if not model_path.is_file() or v1.digest_file(model_path) != v1.MODEL_SHA:
        raise ValueError("model file digest differs")
    commit = protocol["frozen_code_commit"]
    if type(commit) is not str or not COMMIT_RE.fullmatch(commit):
        raise ValueError("frozen commit differs")
    for key, paths in (("source_manifest", SOURCE_PATHS), ("input_hashes", INPUTS)):
        manifest = protocol[key]
        if type(manifest) is not dict or set(manifest) != set(paths):
            raise ValueError(f"{key} differs")
        observed = _manifest(commit, paths)
        if manifest != observed or any(not SHA_RE.fullmatch(value) for value in manifest.values()):
            raise ValueError(f"{key} differs")
    cases = _load_cases(DATA.read_bytes())
    policy = _policy(protocol)
    hashes = protocol["request_sha256_by_call"]
    if type(hashes) is not dict or set(hashes) != set(ORDER):
        raise ValueError("request manifest differs")
    if hashes != {key: _request_sha(cases[key], policy) for key in ORDER}:
        raise ValueError("frozen request differs")
    relative = path.resolve().relative_to(ROOT).as_posix()
    if v4._git("show", f"HEAD:{relative}") != raw:
        raise ValueError("protocol must be committed before model calls")
    v4._clean_checkout()
    return protocol, digest(raw), cases


def _append(stream, row: dict) -> None:
    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def run(args: argparse.Namespace, *, completion_call=v4.post_format_completion) -> None:
    # This protocol has one canonical run. Changing CLI paths must not turn a
    # partial or completed run into a second set of calls with the same hashes.
    if args.output.absolute() != JOURNAL or args.private_dir.absolute() != PRIVATE_DIR:
        raise ValueError("one-shot output paths differ")
    if args.output.exists() or args.private_dir.exists():
        raise FileExistsError("partial or existing run requires manual audit")
    if args.output.resolve().is_relative_to(args.private_dir.resolve()):
        raise ValueError("journal must be outside private directory")
    if not args.output.parent.is_dir() or not os.access(args.output.parent, os.W_OK | os.X_OK):
        raise ValueError("journal parent directory unavailable")
    protocol, protocol_sha, cases = load_protocol(args.protocol, args.model_path)
    if args.container_name != CONTAINER_NAME:
        raise ValueError("container name differs")
    if args.private_dir.is_symlink() or args.private_dir.resolve().is_relative_to(ROOT):
        raise ValueError("private output must be outside repository")
    policy = _policy(protocol)
    v4._verify_local_docker_endpoint()
    identity = v4._container_identity(args.container_name)
    server.verify_container(args.container_name, args.model_path)
    if v4._container_identity(args.container_name) != identity:
        raise ValueError("model server changed during preflight")
    args.private_dir.mkdir(mode=0o700, parents=False)
    args.private_dir.chmod(0o700)
    if stat.S_IMODE(args.private_dir.stat().st_mode) != 0o700:
        raise ValueError("private directory mode differs")
    try:
        stream = args.output.open("x", encoding="utf-8")
    except OSError:
        try:
            args.private_dir.rmdir()
        except OSError:
            pass
        raise
    with stream:
        _append(stream, {"event": "header", "protocol_sha256": protocol_sha})
        for case_id in ORDER:
            case = cases[case_id]
            outgoing = _outgoing(case)
            schema = _schema(case)
            request_sha = digest(v4.request_bytes(outgoing, schema, policy, "variant"))
            if request_sha != protocol["request_sha256_by_call"][case_id]:
                raise ValueError("outgoing request differs from frozen protocol")
            if v4._container_identity(args.container_name) != identity:
                raise ValueError("model server changed before request; manual audit required")
            row = {
                "event": "result",
                "case_id": case_id,
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
                completion = completion_call(
                    outgoing,
                    schema,
                    condition="variant",
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
                        args.private_dir / f"{case_id}.json.txt", completion.content
                    )
                    if completion.finish_reason != "stop":
                        row["error_code"] = "finish_length"
            if v4._container_identity(args.container_name) != identity:
                raise ValueError("model server changed during run; manual audit required")
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
