"""Run the v18 request bytes with an independently pinned local GGUF."""

import argparse
import json
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from experiments.as_safety_atomic_edges_v10.model_attestation import ModelAttestor
from experiments.as_safety_atomic_edges_v18 import run as baseline
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.transport import TransportError, _NoRedirect

v1, v4, v5, v7, v12 = baseline.v1, baseline.v4, baseline.v5, baseline.v7, baseline.v12
MODEL_SHA = "b46661073c18e5b56a41fa320975f866a00def1ff08feef4718e013258896f8c"
BASELINE_JOURNAL_SHA = "f1c3dc0e58c884e8f845b709c1053d655fbe06ae0022f7756ab4b63b5a61e57e"
CONTAINER = "as-safety-eb-model-comparison-v19"
PROTOCOL = baseline.DATA / "as-safety-eb-model-comparison-v19-protocol.json"
JOURNAL = baseline.DATA / "as-safety-eb-model-comparison-v19-journal.v1.jsonl"
PRIVATE_DIR = Path("/private/tmp/as-safety-eb-model-comparison-v19-raw")
SOURCES = (
    "experiments/as_safety_atomic_edges_v19.py",
    "experiments/as_safety_atomic_edges_v18/run.py",
    "docs/portfolio/nlu_safety_eb_evidence_model_comparison_v19_method.md",
)


def manifest(commit, calls):
    hashes = {path: v12._sha(v12._git("show", f"{commit}:{path}")) for path in SOURCES}
    if any(v12._sha((baseline.ROOT / path).read_bytes()) != sha for path, sha in hashes.items()):
        raise ValueError("comparison code differs from frozen source")
    if v12._sha(baseline.JOURNAL.read_bytes()) != BASELINE_JOURNAL_SHA:
        raise ValueError("reference journal differs")
    return {
        "frozen_code_commit": commit,
        "source_sha256": hashes,
        "baseline_protocol_sha256": baseline.load_protocol(calls, replay_only=True),
        "baseline_journal_sha256": BASELINE_JOURNAL_SHA,
        "request_sha256": {name: v12._sha(call[3]) for name, call in calls.items()},
        "order": list(calls),
        "model_sha256": MODEL_SHA,
        "container": CONTAINER,
        "image_digest": v1.IMAGE,
        "server_args": list(v1.SERVER_ARGS),
    }


@contextmanager
def server(model_path):
    driver = v12.v10_run
    v4._verify_local_docker_endpoint()
    if driver._docker("inspect", CONTAINER, check=False).returncode == 0:
        raise ValueError("existing experiment container requires manual audit")
    attestor = ModelAttestor(model_path, MODEL_SHA, CONTAINER)
    driver._docker(
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
    try:
        driver.server.verify_container(CONTAINER, attestor.path)
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
        driver._docker("stop", CONTAINER, check=False)
        driver._docker("rm", CONTAINER, check=False)


def capture(name, call, policy, attestor, gold):
    pair, messages, schema, body = call
    row = {"call": name, "request_sha256": v12._sha(body), "error": None}
    result = None
    started = time.perf_counter()
    try:
        response = baseline.guarded_call(
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
    except TransportError as exc:
        row.update(error=exc.code, http_status=exc.status_code)
    else:
        row["finish_reason"] = response.finish_reason
        row["raw_sha256"], row["raw_bytes"] = v1._write_private_raw(
            PRIVATE_DIR / f"{name}.json.txt", response.content
        )
        if response.finish_reason == "stop":
            try:
                result = baseline.selection.validate_response(response.content, pair)
            except ValidationError as exc:
                row["error"] = exc.code
        else:
            row["error"] = "finish_length"
    return {
        **row,
        "request_latency_ms": round((time.perf_counter() - started) * 1000, 3),
        **baseline.selection.score(pair, gold, result),
        "all_evidence_blank": None
        if result is None
        else all(value is None for value in result["evidence"].values()),
    }


def run(model_path, policy, calls):
    raw = PROTOCOL.read_bytes()
    frozen = json.loads(raw, object_pairs_hook=v4._unique_pairs)
    if frozen != manifest(frozen["frozen_code_commit"], calls):
        raise ValueError("comparison protocol differs")
    if v12._git("show", f"HEAD:{PROTOCOL.relative_to(baseline.ROOT)}") != raw:
        raise ValueError("protocol must be committed before calls")
    labels = {row["call"]: row for row in json.loads(baseline.LABELS.read_bytes())["cases"]}
    with server(model_path) as attestor:
        counts = {
            name: baseline.guarded_call(attestor, lambda body=call[3]: v7._tokenize_request(body))
            for name, call in calls.items()
        }
        if any(
            count + policy.max_tokens >= v1.RUNTIME["context_tokens"] for count in counts.values()
        ):
            raise ValueError("context budget exceeded")
        PRIVATE_DIR.mkdir(mode=0o700)
        with JOURNAL.open("x", encoding="utf-8") as stream:
            v5._append(stream, {"protocol_sha256": v12._sha(raw), "input_tokens": counts})
            for name, call in calls.items():
                row = capture(name, call, policy, attestor, labels[name.rsplit("-", 1)[0]])
                v5._append(stream, row)
                if row["error"] is not None:
                    break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("--model-path", type=Path, required=True)
    args = parser.parse_args()
    if JOURNAL.exists() or PRIVATE_DIR.exists():
        raise FileExistsError("existing or partial run requires manual audit")
    v12._clean()
    policy, calls = baseline.calls()
    if args.command == "run":
        run(args.model_path, policy, calls)
        return
    if v1.digest_file(args.model_path) != MODEL_SHA:
        raise ValueError("comparison model bytes differ")
    frozen = manifest(v12._git("rev-parse", "HEAD").decode().strip(), calls)
    with PROTOCOL.open("x", encoding="utf-8") as stream:
        json.dump(frozen, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
