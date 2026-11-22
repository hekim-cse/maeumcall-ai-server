"""Freeze and run four reviewed, exposed candidate-relation development calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
import time
from functools import lru_cache
from pathlib import Path

from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v4 import run as v4
from experiments.as_safety_atomic_edges_v5 import run as v5
from experiments.as_safety_atomic_edges_v7 import run as v7
from experiments.as_safety_atomic_edges_v10 import probe
from experiments.as_safety_atomic_edges_v10 import run as v10_run
from experiments.as_safety_atomic_edges_v10.model_attestation import guarded_call
from experiments.as_safety_atomic_edges_v12 import pair_contract
from experiments.as_safety_v2.transport import TransportError

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = (
    ROOT / "evals/structured_nlu/data/ai_heldout/as-safety-eb-pair-v12-development-protocol.json"
)
JOURNAL = (
    ROOT / "evals/structured_nlu/data/ai_heldout/as-safety-eb-pair-v12-development-journal.v1.jsonl"
)
PRIVATE_DIR = Path("/private/tmp/as-safety-eb-pair-v12-raw")
ORDER = (("PC01", "P014"), ("PC01", "P016"), ("NC01", "P020"), ("NC01", "P002"))
KIND = "as_safety_eb_pair_v12_development_v1"
SOURCES = tuple(
    sorted(
        v5.SOURCE_PATHS
        | {
            "docs/portfolio/nlu_safety_eb_pair_relation_v12_design.md",
            "docs/portfolio/nlu_safety_eb_pair_relation_v12_review.md",
            "evals/structured_nlu/data/ai_heldout/as-safety-eb-pair-v12-reviewed.json",
            "experiments/as_safety_v2/source_lattice.py",
            "experiments/as_safety_atomic_edges_v7/run.py",
            "experiments/as_safety_atomic_edges_v8/boundary_audit.py",
            "experiments/as_safety_atomic_edges_v9/verify.py",
            "experiments/as_safety_atomic_edges_v10/candidate_contract.py",
            "experiments/as_safety_atomic_edges_v10/model_attestation.py",
            "experiments/as_safety_atomic_edges_v10/probe.py",
            "experiments/as_safety_atomic_edges_v10/run.py",
            "experiments/as_safety_atomic_edges_v12/pair_contract.py",
            "experiments/as_safety_atomic_edges_v12/run.py",
            "experiments/as_safety_atomic_edges_v12/verify.py",
            "tests/test_as_safety_pair_relation_v12.py",
            "tests/test_as_safety_pair_run_v12.py",
        }
    )
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _git(*args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=ROOT, check=True, capture_output=True).stdout


def _clean() -> None:
    if _git("-c", "core.fsmonitor=false", "status", "--porcelain").strip():
        raise ValueError("checkout must be clean")


@lru_cache(maxsize=1)
def _kiwi() -> Kiwi:
    return Kiwi()


def _pair_name(case_id: str, candidate_id: str) -> str:
    return f"{case_id}-{candidate_id}"


def _requests(cases: dict, policy) -> dict[str, bytes]:
    result = {}
    for case_id, candidate_id in ORDER:
        pair = pair_contract.fixed_pair(cases[case_id], candidate_id, _kiwi())
        result[_pair_name(case_id, candidate_id)] = v4.request_bytes(
            pair_contract.messages(pair), pair_contract.schema(pair), policy, "variant"
        )
    return result


def prepare(model_path: Path) -> None:
    if PROTOCOL.exists() or JOURNAL.exists() or PRIVATE_DIR.exists():
        raise FileExistsError("existing or partial probe requires manual audit")
    _clean()
    commit = _git("rev-parse", "HEAD").decode().strip()
    cases = probe.cases()
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    requests = _requests(cases, policy)
    with v10_run._server(model_path) as attestor:
        tokens = {
            name: guarded_call(attestor, lambda body=body: v7._tokenize_request(body))
            for name, body in requests.items()
        }
    if any(count + policy.max_tokens >= v1.RUNTIME["context_tokens"] for count in tokens.values()):
        raise ValueError("request exceeds context")
    sources = {path: _sha(_git("show", f"{commit}:{path}")) for path in SOURCES}
    if sources != {path: _sha((ROOT / path).read_bytes()) for path in SOURCES}:
        raise ValueError("source differs from committed code")
    payload = {
        "kind": KIND,
        "scope": "four_exposed_user_reviewed_candidate_pairs_development_only",
        "order": [_pair_name(*item) for item in ORDER],
        "frozen_code_commit": commit,
        "source_sha256": sources,
        "cases_sha256": _sha(v5.DATA.read_bytes()),
        "model_sha256": v1.MODEL_SHA,
        "image_digest": v1.IMAGE,
        "container_name": v10_run.CONTAINER,
        "server_args": list(v1.SERVER_ARGS),
        "request_policy": v1.REQUEST_POLICY,
        "retry_policy": v1.RETRY_POLICY,
        "request_sha256": {name: _sha(body) for name, body in requests.items()},
        "input_tokens": tokens,
        "max_context_tokens": v1.RUNTIME["context_tokens"],
        "journal": JOURNAL.relative_to(ROOT).as_posix(),
        "private_output": "outside_repository_mode_0700_files_0600",
    }
    with PROTOCOL.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def _load_protocol() -> tuple[dict, str, dict, object, dict[str, bytes]]:
    raw = PROTOCOL.read_bytes()
    protocol = json.loads(raw, object_pairs_hook=v4._unique_pairs)
    order = [_pair_name(*item) for item in ORDER]
    expected_fields = {
        "kind",
        "scope",
        "order",
        "frozen_code_commit",
        "source_sha256",
        "cases_sha256",
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
        or set(protocol) != expected_fields
        or protocol["kind"] != KIND
        or protocol["order"] != order
        or protocol["container_name"] != v10_run.CONTAINER
        or protocol["journal"] != JOURNAL.relative_to(ROOT).as_posix()
        or protocol["private_output"] != "outside_repository_mode_0700_files_0600"
        or protocol["model_sha256"] != v1.MODEL_SHA
        or protocol["image_digest"] != v1.IMAGE
        or protocol["server_args"] != list(v1.SERVER_ARGS)
        or protocol["request_policy"] != v1.REQUEST_POLICY
        or protocol["retry_policy"] != v1.RETRY_POLICY
        or protocol["max_context_tokens"] != v1.RUNTIME["context_tokens"]
        or set(protocol["source_sha256"]) != set(SOURCES)
    ):
        raise ValueError("protocol identity differs")
    commit = protocol["frozen_code_commit"]
    for path, digest in protocol["source_sha256"].items():
        if digest != _sha(_git("show", f"{commit}:{path}")) or digest != _sha(
            (ROOT / path).read_bytes()
        ):
            raise ValueError("frozen source differs")
    if protocol["cases_sha256"] != _sha(v5.DATA.read_bytes()):
        raise ValueError("reviewed source differs")
    cases = probe.cases()
    policy = v5._policy(protocol)
    requests = _requests(cases, policy)
    if protocol["request_sha256"] != {name: _sha(body) for name, body in requests.items()}:
        raise ValueError("frozen requests differ")
    if set(protocol["input_tokens"]) != set(order) or any(
        type(count) is not int
        or count <= 0
        or count + policy.max_tokens >= v1.RUNTIME["context_tokens"]
        for count in protocol["input_tokens"].values()
    ):
        raise ValueError("frozen token budget differs")
    if _git("show", f"HEAD:{PROTOCOL.relative_to(ROOT).as_posix()}") != raw:
        raise ValueError("protocol must be committed before calls")
    _clean()
    return protocol, _sha(raw), cases, policy, requests


def run(model_path: Path) -> None:
    if JOURNAL.exists() or PRIVATE_DIR.exists():
        raise FileExistsError("existing or partial run requires manual audit")
    protocol, protocol_sha, cases, policy, requests = _load_protocol()
    with v10_run._server(model_path) as attestor:
        for name, body in requests.items():
            count = guarded_call(attestor, lambda body=body: v7._tokenize_request(body))
            if count != protocol["input_tokens"][name]:
                raise ValueError("tokenizer count differs")
        PRIVATE_DIR.mkdir(mode=0o700)
        if stat.S_IMODE(PRIVATE_DIR.stat().st_mode) != 0o700:
            raise ValueError("private directory mode differs")
        with JOURNAL.open("x", encoding="utf-8") as stream:
            v5._append(stream, {"event": "header", "protocol_sha256": protocol_sha})
            for case_id, candidate_id in ORDER:
                name = _pair_name(case_id, candidate_id)
                pair = pair_contract.fixed_pair(cases[case_id], candidate_id, _kiwi())
                row = {
                    "event": "result",
                    "call": name,
                    "request_sha256": _sha(requests[name]),
                    "finish_reason": None,
                    "error_code": None,
                    "http_status": None,
                    "raw_sha256": None,
                    "raw_bytes": None,
                    "request_latency_ms": None,
                }
                started = time.perf_counter()
                try:
                    completion = guarded_call(
                        attestor,
                        lambda pair=pair: v4.post_format_completion(
                            pair_contract.messages(pair),
                            pair_contract.schema(pair),
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
                        PRIVATE_DIR / f"{name}.json.txt", completion.content
                    )
                    if completion.finish_reason != "stop":
                        row["error_code"] = "finish_length"
                row["request_latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
                v5._append(stream, row)
                if row["error_code"] is not None:
                    break


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
