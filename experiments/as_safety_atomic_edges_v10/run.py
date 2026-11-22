"""Prepare and execute two frozen candidate-ID development calls once."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v4 import run as v4
from experiments.as_safety_atomic_edges_v5 import run as v5
from experiments.as_safety_atomic_edges_v7 import run as v7
from experiments.as_safety_atomic_edges_v10 import probe
from experiments.as_safety_atomic_edges_v10.model_attestation import (
    ModelAttestor,
    guarded_call,
)
from experiments.as_safety_v2.transport import TransportError, _NoRedirect
from experiments.as_safety_v4 import run as server

ROOT = Path(__file__).resolve().parents[2]
METHOD = ROOT / "docs/portfolio/nlu_safety_eb_candidate_id_v10_method.md"
PROTOCOL = (
    ROOT
    / "evals/structured_nlu/data/ai_heldout/as-safety-eb-candidate-id-v10-development-protocol.json"
)
JOURNAL = (
    ROOT
    / "evals/structured_nlu/data/ai_heldout/as-safety-eb-candidate-id-v10-development-journal.v1.jsonl"
)
PRIVATE_DIR = Path("/private/tmp/as-safety-eb-candidate-id-v10-raw")
CONTAINER = "as-safety-eb-candidate-id-v10"
KIND = "as_safety_eb_candidate_id_v10_development_v1"
SOURCES = tuple(
    sorted(
        v5.SOURCE_PATHS
        | {
            "docs/portfolio/nlu_safety_eb_candidate_id_v10_method.md",
            "experiments/as_safety_v2/source_lattice.py",
            "experiments/as_safety_atomic_edges_v7/run.py",
            "experiments/as_safety_atomic_edges_v8/boundary_audit.py",
            "experiments/as_safety_atomic_edges_v9/verify.py",
            "experiments/as_safety_atomic_edges_v10/candidate_contract.py",
            "experiments/as_safety_atomic_edges_v10/model_attestation.py",
            "experiments/as_safety_atomic_edges_v10/probe.py",
            "experiments/as_safety_atomic_edges_v10/run.py",
            "experiments/as_safety_atomic_edges_v10/verify.py",
            "tests/test_as_safety_candidate_id_probe_v10.py",
        }
    )
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _git(*args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=ROOT, check=True, capture_output=True).stdout


def _frozen(commit: str, relative: str) -> bytes:
    if not (len(commit) == 40 and all(c in "0123456789abcdef" for c in commit)):
        raise ValueError("frozen commit invalid")
    return _git("show", f"{commit}:{relative}")


def _clean() -> None:
    if _git("status", "--porcelain").strip():
        raise ValueError("checkout must be clean")


def _docker(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ("docker", *args), check=check, capture_output=True, text=True, timeout=120
    )


@contextmanager
def _server(model_path: Path):
    v4._verify_local_docker_endpoint()
    if _docker("inspect", CONTAINER, check=False).returncode == 0:
        raise ValueError("existing model container requires manual audit")
    attestor = ModelAttestor(model_path, v1.MODEL_SHA, CONTAINER)
    started = False
    try:
        _docker(
            "run",
            "-d",
            "--name",
            CONTAINER,
            "--cpus",
            "2",
            "--memory",
            str(v1.RUNTIME["memory_bytes"]),
            "-p",
            "127.0.0.1:18081:8080",
            "-v",
            f"{attestor.path}:/models/kanana.gguf:ro",
            v1.IMAGE,
            *v1.SERVER_ARGS,
        )
        started = True
        server.verify_container(CONTAINER, attestor.path)
        attestor.activate()
        opener = build_opener(ProxyHandler({}), _NoRedirect())
        for _ in range(60):
            try:
                with opener.open("http://127.0.0.1:18081/health", timeout=2) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(2)
        else:
            raise ValueError("model server health unavailable")
        attestor.check()
        yield attestor
    finally:
        if started:
            _docker("stop", CONTAINER, check=False)
            _docker("rm", CONTAINER, check=False)


def _requests(cases: dict, policy) -> dict[str, bytes]:
    return {name: probe.request_bytes(cases[name], policy) for name in probe.CASE_ORDER}


def _manifest(cases: dict) -> dict:
    return {
        name: {
            "candidate_ids": [c.id for c in probe.catalog(cases[name]).candidates],
            "candidate_rows_sha256": _sha(
                "\n".join(
                    f"{c.id} | {c.clause_index}번 | {c.quote}"
                    for c in probe.catalog(cases[name]).candidates
                ).encode("utf-8")
            ),
        }
        for name in probe.CASE_ORDER
    }


def prepare(model_path: Path) -> dict:
    if PROTOCOL.exists() or JOURNAL.exists() or PRIVATE_DIR.exists():
        raise FileExistsError("existing or partial probe requires manual audit")
    _clean()
    commit = _git("rev-parse", "HEAD").decode().strip()
    cases = probe.cases()
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    requests = _requests(cases, policy)
    with _server(model_path) as attestor:
        counts = {}
        for name, body in requests.items():
            counts[name] = guarded_call(attestor, lambda body=body: v7._tokenize_request(body))
            if counts[name] + policy.max_tokens >= v1.RUNTIME["context_tokens"]:
                raise ValueError("request exceeds context")
    payload = {
        "kind": KIND,
        "scope": "two_exposed_ai_authored_reviewed_development_controls",
        "order": list(probe.CASE_ORDER),
        "frozen_code_commit": commit,
        "source_sha256": {path: _sha(_frozen(commit, path)) for path in SOURCES},
        "cases_sha256": _sha(v5.DATA.read_bytes()),
        "model_sha256": v1.MODEL_SHA,
        "image_digest": v1.IMAGE,
        "server_args": list(v1.SERVER_ARGS),
        "request_policy": v1.REQUEST_POLICY,
        "candidate_manifest": _manifest(cases),
        "request_sha256": {name: _sha(body) for name, body in requests.items()},
        "input_tokens": counts,
        "max_context_tokens": v1.RUNTIME["context_tokens"],
        "retry_policy": v1.RETRY_POLICY,
        "journal": JOURNAL.relative_to(ROOT).as_posix(),
        "private_output": "outside_repository_mode_0700_files_0600",
    }
    with PROTOCOL.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    return payload


def _load_protocol() -> tuple[dict, str, dict, object, dict[str, bytes]]:
    raw = PROTOCOL.read_bytes()
    protocol = json.loads(raw, object_pairs_hook=v4._unique_pairs)
    if (
        type(protocol) is not dict
        or set(protocol)
        != {
            "kind",
            "scope",
            "order",
            "frozen_code_commit",
            "source_sha256",
            "cases_sha256",
            "model_sha256",
            "image_digest",
            "server_args",
            "request_policy",
            "candidate_manifest",
            "request_sha256",
            "input_tokens",
            "max_context_tokens",
            "retry_policy",
            "journal",
            "private_output",
        }
        or protocol["kind"] != KIND
        or protocol["order"] != list(probe.CASE_ORDER)
        or protocol["journal"] != JOURNAL.relative_to(ROOT).as_posix()
        or protocol["private_output"] != "outside_repository_mode_0700_files_0600"
        or protocol["max_context_tokens"] != v1.RUNTIME["context_tokens"]
    ):
        raise ValueError("protocol identity differs")
    commit = protocol["frozen_code_commit"]
    if protocol["source_sha256"] != {path: _sha(_frozen(commit, path)) for path in SOURCES}:
        raise ValueError("frozen source differs")
    if protocol["source_sha256"] != {path: _sha((ROOT / path).read_bytes()) for path in SOURCES}:
        raise ValueError("current source differs from frozen code")
    if protocol["cases_sha256"] != _sha(v5.DATA.read_bytes()):
        raise ValueError("reviewed input differs")
    if protocol["model_sha256"] != v1.MODEL_SHA or protocol["image_digest"] != v1.IMAGE:
        raise ValueError("model identity differs")
    if (
        protocol["server_args"] != list(v1.SERVER_ARGS)
        or protocol["retry_policy"] != v1.RETRY_POLICY
    ):
        raise ValueError("runtime or retry policy differs")
    if protocol["request_policy"] != v1.REQUEST_POLICY:
        raise ValueError("request policy differs")
    cases = probe.cases()
    policy = v5._policy(protocol)
    requests = _requests(cases, policy)
    if protocol["candidate_manifest"] != _manifest(cases):
        raise ValueError("candidate manifest differs")
    if protocol["request_sha256"] != {name: _sha(body) for name, body in requests.items()}:
        raise ValueError("request bytes differ")
    if set(protocol["input_tokens"]) != set(probe.CASE_ORDER) or any(
        type(count) is not int
        or count <= 0
        or count + policy.max_tokens >= v1.RUNTIME["context_tokens"]
        for count in protocol["input_tokens"].values()
    ):
        raise ValueError("input token budget differs")
    if _git("show", f"HEAD:{PROTOCOL.relative_to(ROOT).as_posix()}") != raw:
        raise ValueError("protocol must be committed before calls")
    _clean()
    return protocol, _sha(raw), cases, policy, requests


def run(model_path: Path) -> None:
    if JOURNAL.exists() or PRIVATE_DIR.exists():
        raise FileExistsError("existing or partial run requires manual audit")
    protocol, protocol_sha, cases, policy, requests = _load_protocol()
    with _server(model_path) as attestor:
        for name, body in requests.items():
            count = guarded_call(attestor, lambda body=body: v7._tokenize_request(body))
            if count != protocol["input_tokens"][name]:
                raise ValueError("tokenizer count differs")
        PRIVATE_DIR.mkdir(mode=0o700)
        PRIVATE_DIR.chmod(0o700)
        if stat.S_IMODE(PRIVATE_DIR.stat().st_mode) != 0o700:
            raise ValueError("private directory mode differs")
        with JOURNAL.open("x", encoding="utf-8") as stream:
            v5._append(stream, {"event": "header", "protocol_sha256": protocol_sha})
            for name in probe.CASE_ORDER:
                case = cases[name]
                selected = probe.catalog(case)
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
                        lambda case=case, selected=selected: v4.post_format_completion(
                            probe.messages(case, selected),
                            selected.schema(),
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
