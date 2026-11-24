"""Swap the displayed sentence IDs in the frozen v20 requests."""

import argparse
import json
import stat
from pathlib import Path

from experiments import as_safety_atomic_edges_v20 as baseline
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.transport import TransportError

runtime = baseline.runtime
git, sha = runtime.v12._git, runtime.v12._sha
PREFIX = "as-safety-eb-source-id-swap-v21"
PROTOCOL = baseline.baseline.DATA / f"{PREFIX}-protocol.json"
JOURNAL = baseline.baseline.DATA / f"{PREFIX}-journal.v1.jsonl"
PRIVATE_DIR = Path("/private/tmp") / f"{PREFIX}-raw"
METHOD = "docs/portfolio/nlu_safety_eb_source_id_swap_v21_method.md"
SOURCES = ("experiments/as_safety_atomic_edges_v21.py", METHOD)
SWAP = str.maketrans("12", "21")


def remap(pair, messages):
    lines = messages[1]["content"].splitlines()
    event, candidate = pair.event, pair.candidate
    original = [
        "번호가 붙은 원문 근거 후보:",
        *(f"{i}. {text}" for i, text in enumerate(pair.clauses, 1)),
        f"위험 사건 E: {event['clause_index']}번 | {event['quote']}",
        f"후보 B: {candidate.id} | {candidate.clause_index}번 | {candidate.quote}",
    ]
    if lines[: len(original)] != original or event["clause_index"] != 2:
        raise ValueError("unexpected baseline message")
    lines[1] = "2" + lines[1][1:]
    lines[2] = "1" + lines[2][1:]
    lines[len(original) - 2] = lines[len(original) - 2].replace("E: 2번", "E: 1번", 1)
    candidate_line = len(original) - 1
    number = str(candidate.clause_index)
    display = number.translate(SWAP) if number in {"1", "2"} else number
    lines[candidate_line] = lines[candidate_line].replace(
        f" | {number}번 | ", f" | {display}번 | ", 1
    )
    return [messages[0], {**messages[1], "content": "\n".join(lines)}]


def requests():
    policy, old = baseline.requests()
    baseline_sha = baseline.load_protocol(old)
    if (
        sha(baseline.JOURNAL.read_bytes())
        != "2866d8b2138066b58d0bad1e08bfe0edd94da71554e9d4b44d8f91a0b6cbceb5"
    ):
        raise ValueError("v20 journal differs")
    calls = {}
    for name, (pair, messages, schema, _) in old.items():
        swapped = remap(pair, messages)
        calls[name] = (
            pair,
            swapped,
            schema,
            runtime.v4.request_bytes(swapped, schema, policy, "variant"),
        )
    return policy, calls, baseline_sha


def manifest(commit, calls, baseline_sha):
    frozen = {path: sha(git("show", f"{commit}:{path}")) for path in SOURCES}
    if any(
        sha((baseline.baseline.ROOT / path).read_bytes()) != digest
        for path, digest in frozen.items()
    ):
        raise ValueError("frozen sources differ")
    return {
        "commit": commit,
        "source_sha256": frozen,
        "v20_protocol_sha256": baseline_sha,
        "model_sha256": runtime.MODEL_SHA,
        "image_digest": runtime.v1.IMAGE,
        "order": list(calls),
        "request_sha256": {name: sha(call[3]) for name, call in calls.items()},
    }


def verified_protocol(calls, baseline_sha):
    raw = PROTOCOL.read_bytes()
    saved = json.loads(raw)
    if saved != manifest(saved["commit"], calls, baseline_sha):
        raise ValueError("protocol differs")
    if raw != git("show", f"HEAD:{PROTOCOL.relative_to(baseline.baseline.ROOT)}"):
        raise ValueError("protocol must be committed before calls")
    return sha(raw)


def capture(name, pair, messages, schema, body, policy, attestor):
    row = {"call": name, "request_sha256": sha(body), "selected": None, "error": None}
    try:
        completion = runtime.baseline.guarded_call(
            attestor,
            lambda: runtime.v4.post_format_completion(
                messages,
                schema,
                condition="variant",
                policy=policy,
                endpoint=runtime.v1.ENDPOINT,
                model_id=runtime.v1.MODEL_ID,
            ),
        )
    except TransportError as exc:
        return {**row, "error": exc.code, "http_status": exc.status_code}
    row["raw_sha256"], row["raw_bytes"] = runtime.v1._write_private_raw(
        PRIVATE_DIR / f"{name}.json.txt", completion.content
    )
    row["finish_reason"] = completion.finish_reason
    selected, error = decode(pair, completion.finish_reason, completion.content)
    return {**row, "selected": selected, "error": error}


def decode(pair, finish, content):
    if finish != "stop":
        return None, "finish_length"
    try:
        return baseline.validate(content, pair), None
    except ValidationError as exc:
        return None, exc.code


def run(model, policy, calls, protocol_sha):
    with runtime.server(model) as attestor:
        counts = {
            name: runtime.baseline.guarded_call(
                attestor, lambda body=call[3]: runtime.v7._tokenize_request(body)
            )
            for name, call in calls.items()
        }
        if any(
            count + policy.max_tokens >= runtime.v1.RUNTIME["context_tokens"]
            for count in counts.values()
        ):
            raise ValueError("context budget exceeded")
        PRIVATE_DIR.mkdir(mode=0o700)
        with JOURNAL.open("x", encoding="utf-8") as stream:
            runtime.v5._append(stream, {"protocol_sha256": protocol_sha, "input_tokens": counts})
            for name, call in calls.items():
                row = capture(name, *call, policy, attestor)
                runtime.v5._append(stream, row)
                if row["error"] is not None:
                    break


def replay(calls, protocol_sha):
    header, *rows = map(json.loads, JOURNAL.read_text(encoding="utf-8").splitlines())
    if (
        header["protocol_sha256"] != protocol_sha
        or [r["call"] for r in rows] != list(calls)[: len(rows)]
    ):
        raise ValueError("journal identity differs")
    if (
        not rows
        or any(r["error"] for r in rows[:-1])
        or (len(rows) < len(calls) and rows[-1]["error"] is None)
    ):
        raise ValueError("inconsistent journal termination")
    if PRIVATE_DIR.is_symlink() or stat.S_IMODE(PRIVATE_DIR.stat().st_mode) != 0o700:
        raise ValueError("private directory differs")
    for row in rows:
        name = row["call"]
        pair, _, _, body = calls[name]
        if row["request_sha256"] != sha(body):
            raise ValueError(f"request differs: {name}")
        if "raw_sha256" not in row:
            if not row["error"] or "http_status" not in row:
                raise ValueError(f"missing completion or transport error: {name}")
            continue
        path = PRIVATE_DIR / f"{name}.json.txt"
        if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise ValueError(f"raw response permissions differ: {name}")
        raw = path.read_bytes()
        if (sha(raw), len(raw)) != (row["raw_sha256"], row["raw_bytes"]):
            raise ValueError(f"raw response differs: {name}")
        if decode(pair, row["finish_reason"], raw.decode()) != (row["selected"], row["error"]):
            raise ValueError(f"outcome differs: {name}")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "replay"))
    parser.add_argument("--model-path", type=Path)
    args = parser.parse_args()
    policy, calls, baseline_sha = requests()
    if args.command == "replay":
        print(json.dumps(replay(calls, verified_protocol(calls, baseline_sha)), indent=2))
        return
    if args.model_path is None:
        parser.error("--model-path is required")
    if JOURNAL.exists() or PRIVATE_DIR.exists():
        raise FileExistsError("existing or partial run requires manual audit")
    runtime.v12._clean()
    if args.command == "run":
        run(args.model_path, policy, calls, verified_protocol(calls, baseline_sha))
        return
    if runtime.v1.digest_file(args.model_path) != runtime.MODEL_SHA:
        raise ValueError("model digest differs")
    with PROTOCOL.open("x", encoding="utf-8") as stream:
        json.dump(
            manifest(git("rev-parse", "HEAD").decode().strip(), calls, baseline_sha),
            stream,
            indent=2,
        )
        stream.write("\n")


if __name__ == "__main__":
    main()
