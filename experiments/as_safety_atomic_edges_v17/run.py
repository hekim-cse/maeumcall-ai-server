"""Freeze and execute the fixed-pair evidence extraction experiment."""

import argparse
import json
import stat
import time
from pathlib import Path

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v4 import run as v4
from experiments.as_safety_atomic_edges_v5 import run as v5
from experiments.as_safety_atomic_edges_v7 import run as v7
from experiments.as_safety_atomic_edges_v10 import probe
from experiments.as_safety_atomic_edges_v10.model_attestation import guarded_call
from experiments.as_safety_atomic_edges_v12 import pair_contract
from experiments.as_safety_atomic_edges_v12 import run as v12
from experiments.as_safety_atomic_edges_v17 import evidence_contract
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.transport import TransportError

ROOT = v12.ROOT
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
PROTOCOL = DATA / "as-safety-eb-evidence-first-v17-protocol.json"
JOURNAL = DATA / "as-safety-eb-evidence-first-v17-journal.v1.jsonl"
PRIVATE_DIR = Path("/private/tmp/as-safety-eb-evidence-first-v17-raw")
LABELS = DATA / "as-safety-eb-pair-v12-reviewed.json"
SOURCES = sorted(
    set(v12.SOURCES)
    | {
        "docs/portfolio/nlu_safety_eb_evidence_first_v17_method.md",
        "experiments/as_safety_atomic_edges_v17/__init__.py",
        "experiments/as_safety_atomic_edges_v17/evidence_contract.py",
        "experiments/as_safety_atomic_edges_v17/run.py",
        "tests/test_as_safety_evidence_first_v17.py",
    }
)


def calls():
    cases = probe.cases()
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    result = {}
    for case_id, candidate_id in v12.ORDER:
        pair = pair_contract.fixed_pair(cases[case_id], candidate_id, v12._kiwi())
        schema = evidence_contract.schema(pair)
        for order in ("forward", "reverse"):
            name = f"{v12._pair_name(case_id, candidate_id)}-{order}"
            messages = evidence_contract.messages(pair, reverse_questions=order == "reverse")
            body = v4.request_bytes(messages, schema, policy, "variant")
            result[name] = (pair, messages, schema, body)
    return policy, result


def manifest(commit, requests):
    sources = {path: v12._sha(v12._git("show", f"{commit}:{path}")) for path in SOURCES}
    if sources != {path: v12._sha((ROOT / path).read_bytes()) for path in SOURCES}:
        raise ValueError("frozen source differs")
    return {
        "kind": "as_safety_eb_evidence_first_v17_development",
        "frozen_code_commit": commit,
        "source_sha256": sources,
        "order": list(requests),
        "request_sha256": {name: v12._sha(call[3]) for name, call in requests.items()},
        "model_sha256": v1.MODEL_SHA,
        "image_digest": v1.IMAGE,
        "container_name": v12.v10_run.CONTAINER,
        "server_args": list(v1.SERVER_ARGS),
        "request_policy": v1.REQUEST_POLICY,
        "retry_policy": v1.RETRY_POLICY,
        "max_context_tokens": v1.RUNTIME["context_tokens"],
    }


def ensure_unused():
    if JOURNAL.exists() or PRIVATE_DIR.exists():
        raise FileExistsError("existing or partial run requires manual audit")


def prepare(model_path):
    ensure_unused()
    v12._clean()
    if v1.digest_file(model_path) != v1.MODEL_SHA:
        raise ValueError("model file differs")
    _, requests = calls()
    payload = manifest(v12._git("rev-parse", "HEAD").decode().strip(), requests)
    with PROTOCOL.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def load_protocol(requests):
    raw = PROTOCOL.read_bytes()
    protocol = json.loads(raw, object_pairs_hook=v4._unique_pairs)
    if protocol != manifest(protocol["frozen_code_commit"], requests):
        raise ValueError("protocol differs from reconstructed requests")
    if v12._git("show", f"HEAD:{PROTOCOL.relative_to(ROOT)}") != raw:
        raise ValueError("protocol must be committed before calls")
    return v12._sha(raw)


def run(model_path):
    ensure_unused()
    v12._clean()
    policy, requests = calls()
    protocol_sha = load_protocol(requests)
    with v12.v10_run._server(model_path) as attestor:
        counts = {
            name: guarded_call(attestor, lambda body=call[3]: v7._tokenize_request(body))
            for name, call in requests.items()
        }
        if any(
            count + policy.max_tokens >= v1.RUNTIME["context_tokens"] for count in counts.values()
        ):
            raise ValueError("request exceeds context")
        PRIVATE_DIR.mkdir(mode=0o700)
        with JOURNAL.open("x", encoding="utf-8") as stream:
            v5._append(
                stream, {"event": "header", "protocol_sha256": protocol_sha, "input_tokens": counts}
            )
            for name, (pair, messages, schema, body) in requests.items():
                row = execute(pair, messages, schema, policy, attestor, name)
                v5._append(
                    stream,
                    {"event": "result", "call": name, "request_sha256": v12._sha(body), **row},
                )
                if row["error_code"] is not None:
                    break


def execute(pair, messages, schema, policy, attestor, name):
    row = dict.fromkeys(("finish_reason", "raw_sha256", "raw_bytes", "error_code", "http_status"))
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
            PRIVATE_DIR / f"{name}.json.txt", completion.content
        )
        if completion.finish_reason != "stop":
            row["error_code"] = "finish_length"
        else:
            try:
                evidence_contract.validate_response(completion.content, pair)
            except ValidationError as error:
                row["error_code"] = error.code
    row["request_latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return row


def replay():
    """Verify journal provenance and rescore the stored responses offline."""
    _, requests = calls()
    protocol_sha = load_protocol(requests)
    with JOURNAL.open(encoding="utf-8") as stream:
        header, *rows = [json.loads(line, object_pairs_hook=v4._unique_pairs) for line in stream]
    if header["event"] != "header" or header["protocol_sha256"] != protocol_sha:
        raise ValueError("journal protocol differs")
    if set(header["input_tokens"]) != set(requests):
        raise ValueError("journal token counts incomplete")
    if [row["call"] for row in rows] != list(requests)[: len(rows)]:
        raise ValueError("journal call order differs")
    if any(row["error_code"] is not None for row in rows[:-1]):
        raise ValueError("journal continued after an error")
    if not rows or (len(rows) < len(requests) and rows[-1]["error_code"] is None):
        raise ValueError("journal ended without a recorded error")
    if PRIVATE_DIR.is_symlink() or stat.S_IMODE(PRIVATE_DIR.stat().st_mode) != 0o700:
        raise ValueError("private directory mode differs")
    labels = {row["call"]: row for row in json.loads(LABELS.read_bytes())["cases"]}
    results = []
    for row in rows:
        name = row["call"]
        pair, _, _, body = requests[name]
        if row["event"] != "result" or row["request_sha256"] != v12._sha(body):
            raise ValueError(f"journal request differs: {name}")
        if row["raw_sha256"] is None:
            if row["error_code"] is None or row["finish_reason"] is not None:
                raise ValueError(f"missing raw response: {name}")
            results.append({"call": name, "error": row["error_code"]})
            continue
        path = PRIVATE_DIR / f"{name}.json.txt"
        if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise ValueError(f"private response mode differs: {name}")
        raw = path.read_bytes()
        if len(raw) != row["raw_bytes"] or v12._sha(raw) != row["raw_sha256"]:
            raise ValueError(f"raw response differs: {name}")
        error = "finish_length" if row["finish_reason"] != "stop" else None
        result = None
        if error is None:
            try:
                result = evidence_contract.validate_response(raw.decode("utf-8"), pair)
            except ValidationError as exc:
                error = exc.code
        if error != row["error_code"]:
            raise ValueError(f"replayed error differs: {name}")
        if result is None:
            results.append({"call": name, "error": error})
            continue
        gold = labels[name.rsplit("-", 1)[0]]
        results.append(
            {
                "call": name,
                "status_match": result["relation_status"] == gold["relation_status"],
                "clause_match": result["evidence_clause_index"] == gold["evidence_clause_index"],
                "relation_status": result["relation_status"],
                "evidence_clause_index": result["evidence_clause_index"],
            }
        )
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "replay"))
    parser.add_argument("--model-path", type=Path)
    args = parser.parse_args()
    if args.command == "replay":
        print(json.dumps(replay(), indent=2))
        return
    if args.model_path is None:
        parser.error("--model-path is required for prepare and run")
    action = prepare if args.command == "prepare" else run
    action(args.model_path)


if __name__ == "__main__":
    main()
