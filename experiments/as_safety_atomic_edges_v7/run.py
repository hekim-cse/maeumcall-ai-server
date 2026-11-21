"""Freeze and run six source-only E→B candidate-order controls exactly once."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v4 import run as v4
from experiments.as_safety_atomic_edges_v5 import run as v5
from experiments.as_safety_v2.source_lattice import generate_source_lattice
from experiments.as_safety_v2.transport import RequestPolicy, TransportError, _NoRedirect
from experiments.as_safety_v4 import run as server

ROOT = Path(__file__).resolve().parents[2]
METHOD = ROOT / "docs/portfolio/nlu_safety_eb_candidate_order_v7_method.md"
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
    "method_v7": METHOD,
    "reviewed_v5_cases": v5.DATA,
    "reference_v5_protocol": REFERENCE_PROTOCOL,
    "reference_v5_journal": REFERENCE_JOURNAL,
}
SOURCE_PATHS = v5.SOURCE_PATHS | {
    "experiments/as_safety_v2/source_lattice.py",
    "experiments/as_safety_atomic_edges_v7/__init__.py",
    "experiments/as_safety_atomic_edges_v7/run.py",
    "experiments/as_safety_atomic_edges_v7/verify.py",
    "tests/test_as_safety_atomic_edge_candidate_order_v7.py",
}
KIND = "as_safety_eb_candidate_order_v7_development_v1"
SCOPE = "source_only_candidate_order_controls_two_exposed_cases"
ORDER = ("PC01-A", "PC01-B", "PC01-C", "NC01-C", "NC01-B", "NC01-A")
CONTAINER_NAME = "as-safety-eb-candidate-order-v7"
JOURNAL = (
    ROOT
    / "evals/structured_nlu/data/ai_heldout/as-safety-eb-candidate-order-v7-development-journal.v1.jsonl"
)
PRIVATE_DIR = Path("/private/tmp/as-safety-eb-candidate-order-v7-raw")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
CANDIDATE_POLICY = {"max_window_tokens": 5, "max_candidates": 192}
TOKENIZE_PATH = "/v1/chat/completions/input_tokens"
CONTEXT_TOKENS = 4096


def _reference() -> None:
    if (
        v5.digest(REFERENCE_PROTOCOL.read_bytes()) != REFERENCE_PROTOCOL_SHA
        or v5.digest(REFERENCE_JOURNAL.read_bytes()) != REFERENCE_JOURNAL_SHA
    ):
        raise ValueError("v5 reference digest differs")


def _cases(raw: bytes) -> dict[str, dict]:
    return v5._load_cases(raw)


def _candidate_rows(case: dict) -> list[str]:
    lattice = generate_source_lattice(case["user_message"], **CANDIDATE_POLICY)
    if not lattice.candidates:
        raise ValueError("source-only candidate list is empty")
    if lattice.truncated:
        raise ValueError("source-only candidate list was truncated")
    return [f"{item.id} | {item.clause_index}번 | {item.quote}" for item in lattice.candidates]


def messages(case: dict, arm: str) -> list[dict[str, str]]:
    if arm not in {"A", "B", "C"}:
        raise ValueError("unknown candidate arm")
    event = {"event_span": case["event_span"], "occurrence": case["occurrence"]}
    base = v4.messages(case, event, "variant")
    if arm == "A":
        return base
    rows = _candidate_rows(case)
    if arm == "C":
        rows.reverse()
    cue = (
        "\n아래는 원문에서 자동 생성한 구절 후보입니다. 후보는 정답 표시가 아닙니다. "
        "실제 위험이 발생한 물리적 출처를 확인할 수 있으면 후보의 원문 구절과 문장 번호를 "
        "subject_span에 사용하세요. 출처를 확인할 수 없다면 subject_span=null, "
        "event_subject_kind=unresolved로 반환하세요. 후보 번호는 출력하지 마세요.\n"
        + "\n".join(rows)
    )
    return [base[0], {"role": "user", "content": base[1]["content"] + cue}]


def request_sha(case: dict, arm: str, policy: RequestPolicy) -> str:
    return v5.digest(v4.request_bytes(messages(case, arm), v5._schema(case), policy, "variant"))


def _candidate_manifest(cases: dict[str, dict]) -> dict[str, dict]:
    result = {}
    for case_id in ("PC01", "NC01"):
        case = cases[case_id]
        lattice = generate_source_lattice(case["user_message"], **CANDIDATE_POLICY)
        rows = _candidate_rows(case)
        result[case_id] = {
            "source_sha256": lattice.source_sha256,
            "candidate_count": len(rows),
            "generated_count": len(lattice.generated),
            "candidate_rows_original_sha256": v5.digest("\n".join(rows).encode("utf-8")),
            "candidate_rows_reversed_sha256": v5.digest("\n".join(reversed(rows)).encode("utf-8")),
        }
    return result


def _tokenize_request(body: bytes) -> int:
    """Ask the pinned local server to count chat-template tokens; fail closed."""
    endpoint = v1.ENDPOINT
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port != v1.RUNTIME["host_port"]
        or parsed.path != "/v1/chat/completions"
    ):
        raise ValueError("tokenizer endpoint is not pinned localhost")
    url = f"http://127.0.0.1:{parsed.port}{TOKENIZE_PATH}"
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=30) as response:
            payload = response.read(4096)
            if response.status != 200:
                raise ValueError("tokenizer endpoint unavailable")
    except (OSError, ValueError, TransportError) as error:
        raise ValueError("tokenizer endpoint unavailable") from error
    try:
        parsed_response = json.loads(payload)
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("tokenizer response invalid") from error
    count = parsed_response.get("input_tokens") if type(parsed_response) is dict else None
    if type(count) is not int or count <= 0:
        raise ValueError("tokenizer count invalid")
    return count


def _token_counts(cases: dict[str, dict], policy: RequestPolicy) -> dict[str, int]:
    if policy.max_tokens != v1.REQUEST_POLICY["max_tokens"]:
        raise ValueError("max output tokens differ")
    counts = {}
    for call in ORDER:
        case = cases[call[:4]]
        body = v4.request_bytes(messages(case, call[-1]), v5._schema(case), policy, "variant")
        count = _tokenize_request(body)
        if count + policy.max_tokens >= CONTEXT_TOKENS:
            raise ValueError("request exceeds model context budget")
        counts[call] = count
    return counts


def _identity() -> dict:
    return {
        "kind": KIND,
        "claim_scope": SCOPE,
        "case_ids": ["PC01", "NC01"],
        "call_order": list(ORDER),
        "response_format": "v4_subject_only_two_field_schema_constrained_json",
        "candidate_generation": CANDIDATE_POLICY,
        "tokenizer_endpoint": TOKENIZE_PATH,
        "context_tokens": CONTEXT_TOKENS,
        "gold_in_requests": False,
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
        "score_scope": "two_exposed_development_controls; no B_to_A; no safety_route",
        "token_usage": "input_tokens_preflight_only; output_tokens_not_collected",
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
    cases = _cases(v5.DATA.read_bytes())
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    v4._verify_local_docker_endpoint()
    identity = v4._container_identity(CONTAINER_NAME)
    server.verify_container(CONTAINER_NAME, model_path)
    token_counts = _token_counts(cases, policy)
    if v4._container_identity(CONTAINER_NAME) != identity:
        raise ValueError("model server changed during tokenizer preflight")
    protocol = {
        **_identity(),
        "frozen_code_commit": commit,
        "source_manifest": source_manifest,
        "input_hashes": input_hashes,
        "candidate_manifest": _candidate_manifest(cases),
        "input_tokens_by_call": token_counts,
        "request_sha256_by_call": {
            call: request_sha(cases[call[:4]], call[-1], policy) for call in ORDER
        },
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
            "candidate_manifest",
            "input_tokens_by_call",
            "request_sha256_by_call",
        }
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
    cases = _cases(v5.DATA.read_bytes())
    policy = v5._policy(protocol)
    if protocol["candidate_manifest"] != _candidate_manifest(cases):
        raise ValueError("candidate manifest differs")
    token_counts = protocol["input_tokens_by_call"]
    if (
        type(token_counts) is not dict
        or set(token_counts) != set(ORDER)
        or any(
            type(count) is not int or count <= 0 or count + policy.max_tokens >= CONTEXT_TOKENS
            for count in token_counts.values()
        )
    ):
        raise ValueError("tokenizer manifest differs")
    hashes = protocol["request_sha256_by_call"]
    if type(hashes) is not dict or set(hashes) != set(ORDER):
        raise ValueError("request manifest differs")
    if hashes != {call: request_sha(cases[call[:4]], call[-1], policy) for call in ORDER}:
        raise ValueError("frozen request differs")
    relative = path.resolve().relative_to(ROOT).as_posix()
    if v4._git("show", f"HEAD:{relative}") != raw:
        raise ValueError("protocol must be committed before model calls")
    v4._clean_checkout()
    return protocol, v5.digest(raw), cases


def run(args: argparse.Namespace, *, completion_call=v4.post_format_completion) -> None:
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
    policy = v5._policy(protocol)
    v4._verify_local_docker_endpoint()
    identity = v4._container_identity(args.container_name)
    server.verify_container(args.container_name, args.model_path)
    if v4._container_identity(args.container_name) != identity:
        raise ValueError("model server changed during preflight")
    if _token_counts(cases, policy) != protocol["input_tokens_by_call"]:
        raise ValueError("live tokenizer count differs from frozen protocol")
    if v4._container_identity(args.container_name) != identity:
        raise ValueError("model server changed during tokenizer preflight")
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
        for call in ORDER:
            case = cases[call[:4]]
            arm = call[-1]
            schema = v5._schema(case)
            outgoing = messages(case, arm)
            request_digest = v5.digest(v4.request_bytes(outgoing, schema, policy, "variant"))
            if request_digest != protocol["request_sha256_by_call"][call]:
                raise ValueError("outgoing request differs from frozen protocol")
            if v4._container_identity(args.container_name) != identity:
                raise ValueError("model server changed before request; manual audit required")
            row = {
                "event": "result",
                "call": call,
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
                        args.private_dir / f"{call}.json.txt", completion.content
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
