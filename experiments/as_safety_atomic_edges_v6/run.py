"""Freeze and run two answer-given E→B format-oracle calls exactly once."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import time
from pathlib import Path

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v4 import run as v4
from experiments.as_safety_atomic_edges_v5 import run as v5
from experiments.as_safety_v2.transport import RequestPolicy, TransportError
from experiments.as_safety_v4 import run as server

ROOT = Path(__file__).resolve().parents[2]
METHOD = ROOT / "docs/portfolio/nlu_safety_atomic_edge_format_oracle_v6_method.md"
REFERENCE_PROTOCOL = (
    ROOT / "evals/structured_nlu/data/ai_heldout/as-safety-eb-controls-v5-development-protocol.json"
)
REFERENCE_JOURNAL = (
    ROOT
    / "evals/structured_nlu/data/ai_heldout/as-safety-eb-controls-v5-development-journal.v1.jsonl"
)
REFERENCE_PROTOCOL_SHA = "9c2733c2faf66051519442e2c6590c3854234481f81330e8fe939606cd1ae95e"
REFERENCE_JOURNAL_SHA = "949b528284b04ee8fbccb9053f4ad428d33b3aaa190d9954d0ab1ecc5cc4dab8"
INPUTS = {
    "method_v6": METHOD,
    "reviewed_v5_cases": v5.DATA,
    "reference_v5_protocol": REFERENCE_PROTOCOL,
    "reference_v5_journal": REFERENCE_JOURNAL,
}
SOURCE_PATHS = v5.SOURCE_PATHS | {
    "experiments/as_safety_atomic_edges_v6/__init__.py",
    "experiments/as_safety_atomic_edges_v6/run.py",
    "experiments/as_safety_atomic_edges_v6/verify.py",
    "tests/test_as_safety_atomic_edge_format_oracle_v6.py",
}
KIND = "as_safety_eb_format_oracle_v6_development_v1"
SCOPE = "answer_given_format_oracle_only_no_extraction_accuracy"
ORDER = ("F1", "F2")
CONTAINER_NAME = "as-safety-eb-format-oracle-v6"
JOURNAL = (
    ROOT
    / "evals/structured_nlu/data/ai_heldout/as-safety-eb-format-oracle-v6-development-journal.v1.jsonl"
)
PRIVATE_DIR = Path("/private/tmp/as-safety-eb-format-oracle-v6-raw")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")


def _reference() -> None:
    if (
        v5.digest(REFERENCE_PROTOCOL.read_bytes()) != REFERENCE_PROTOCOL_SHA
        or v5.digest(REFERENCE_JOURNAL.read_bytes()) != REFERENCE_JOURNAL_SHA
    ):
        raise ValueError("v5 reference digest differs")


def _case(raw: bytes) -> dict:
    return v5._load_cases(raw)["PC01"]


def _gold(case: dict) -> dict:
    # These labels are intentionally shown to the model. They are oracle inputs,
    # never extraction predictions or held-out targets.
    return {
        "subject_span": case["gold_subject_span"],
        "event_subject_kind": case["gold_kind"],
    }


def messages(case: dict, arm: str) -> list[dict[str, str]]:
    if arm not in ORDER:
        raise ValueError("unknown oracle arm")
    event = {"event_span": case["event_span"], "occurrence": case["occurrence"]}
    base = v4.messages(case, event, "variant")
    gold = _gold(case)
    if arm == "F1":
        answer = json.dumps(gold, ensure_ascii=False, separators=(",", ":"))
        cue = f"\n형식 오라클 F1: 정답 JSON 객체는 {answer} 입니다. 두 필드의 값과 구조를 바꾸지 말고 이 객체를 반환하세요."
    else:
        span = gold["subject_span"]
        cue = (
            f"\n형식 오라클 F2: 위험의 물리적 출처 B는 {span['clause_index']}번 문장의 "
            f"{span['quote']}이고 연결 종류는 {gold['event_subject_kind']}입니다. "
            "이 문장 번호, 구절, 종류를 두 필드 JSON 객체에 담아 반환하세요."
        )
    return [base[0], {"role": "user", "content": base[1]["content"] + cue}]


def request_sha(case: dict, arm: str, policy: RequestPolicy) -> str:
    return v5.digest(v4.request_bytes(messages(case, arm), v5._schema(case), policy, "variant"))


def _identity() -> dict:
    return {
        "kind": KIND,
        "claim_scope": SCOPE,
        "case_id": "PC01",
        "call_order": list(ORDER),
        "response_format": "v4_subject_only_two_field_schema_constrained_json",
        "oracle_labels_in_both_requests": True,
        "reference_v5_protocol_sha256": REFERENCE_PROTOCOL_SHA,
        "reference_v5_journal_sha256": REFERENCE_JOURNAL_SHA,
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
        "score_scope": "format_oracle_only; no extraction_accuracy; no B_to_A; no safety_route",
        "token_usage": "not_collected_by_completion_transport",
    }


def prepare_protocol(path: Path, model_path: Path) -> dict:
    if not path.resolve().is_relative_to(ROOT):
        raise ValueError("protocol must be inside repository")
    if path.exists():
        raise FileExistsError("protocol already exists")
    v4._clean_checkout()
    _reference()
    commit = v4._git("rev-parse", "HEAD").decode().strip()
    if not model_path.is_file() or v1.digest_file(model_path) != v1.MODEL_SHA:
        raise ValueError("model file digest differs")
    source_manifest = v5._manifest(commit, SOURCE_PATHS)
    input_hashes = v5._manifest(commit, INPUTS)
    case = _case(v5.DATA.read_bytes())
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    protocol = {
        **_identity(),
        "frozen_code_commit": commit,
        "source_manifest": source_manifest,
        "input_hashes": input_hashes,
        "request_sha256_by_call": {arm: request_sha(case, arm, policy) for arm in ORDER},
    }
    with path.open("x", encoding="utf-8") as stream:
        json.dump(protocol, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    return protocol


def load_protocol(path: Path, model_path: Path) -> tuple[dict, str, dict]:
    raw = path.read_bytes()
    protocol = json.loads(raw, object_pairs_hook=v4._unique_pairs)
    expected = _identity()
    if (
        type(protocol) is not dict
        or set(protocol)
        != set(expected)
        | {"frozen_code_commit", "source_manifest", "input_hashes", "request_sha256_by_call"}
        or any(protocol.get(key) != value for key, value in expected.items())
    ):
        raise ValueError("protocol identity differs")
    if not model_path.is_file() or v1.digest_file(model_path) != v1.MODEL_SHA:
        raise ValueError("model file digest differs")
    commit = protocol["frozen_code_commit"]
    if type(commit) is not str or not COMMIT_RE.fullmatch(commit):
        raise ValueError("frozen commit differs")
    _reference()
    for key, paths in (("source_manifest", SOURCE_PATHS), ("input_hashes", INPUTS)):
        manifest = protocol[key]
        if type(manifest) is not dict or set(manifest) != set(paths):
            raise ValueError(f"{key} differs")
        observed = v5._manifest(commit, paths)
        if manifest != observed or any(
            type(v) is not str or not SHA_RE.fullmatch(v) for v in manifest.values()
        ):
            raise ValueError(f"{key} differs")
    case = _case(v5.DATA.read_bytes())
    policy = v5._policy(protocol)
    hashes = protocol["request_sha256_by_call"]
    if type(hashes) is not dict or set(hashes) != set(ORDER):
        raise ValueError("request manifest differs")
    if hashes != {arm: request_sha(case, arm, policy) for arm in ORDER}:
        raise ValueError("frozen request differs")
    relative = path.resolve().relative_to(ROOT).as_posix()
    if v4._git("show", f"HEAD:{relative}") != raw:
        raise ValueError("protocol must be committed before model calls")
    v4._clean_checkout()
    return protocol, v5.digest(raw), case


def run(args: argparse.Namespace, *, completion_call=v4.post_format_completion) -> None:
    if args.output.absolute() != JOURNAL or args.private_dir.absolute() != PRIVATE_DIR:
        raise ValueError("one-shot output paths differ")
    if args.output.exists() or args.private_dir.exists():
        raise FileExistsError("partial or existing run requires manual audit")
    if args.output.resolve().is_relative_to(args.private_dir.resolve()):
        raise ValueError("journal must be outside private directory")
    if not args.output.parent.is_dir() or not os.access(args.output.parent, os.W_OK | os.X_OK):
        raise ValueError("journal parent directory unavailable")
    protocol, protocol_sha, case = load_protocol(args.protocol, args.model_path)
    if args.container_name != CONTAINER_NAME:
        raise ValueError("container name differs")
    if args.private_dir.is_symlink() or args.private_dir.resolve().is_relative_to(ROOT):
        raise ValueError("private output must be outside repository")
    policy = v5._policy(protocol)
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
        v5._append(stream, {"event": "header", "protocol_sha256": protocol_sha})
        schema = v5._schema(case)
        for arm in ORDER:
            outgoing = messages(case, arm)
            request_digest = v5.digest(v4.request_bytes(outgoing, schema, policy, "variant"))
            if request_digest != protocol["request_sha256_by_call"][arm]:
                raise ValueError("outgoing request differs from frozen protocol")
            if v4._container_identity(args.container_name) != identity:
                raise ValueError("model server changed before request; manual audit required")
            row = {
                "event": "result",
                "arm": arm,
                "request_sha256": request_digest,
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
                        args.private_dir / f"{arm}.json.txt", completion.content
                    )
                    if completion.finish_reason != "stop":
                        row["error_code"] = "finish_length"
            if v4._container_identity(args.container_name) != identity:
                raise ValueError("model server changed during run; manual audit required")
            v5._append(stream, row)


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
