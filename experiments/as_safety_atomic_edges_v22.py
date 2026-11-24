"""Move the event row while keeping its displayed ID and references fixed."""

import argparse
import json
import stat
from pathlib import Path

from experiments import as_safety_atomic_edges_v21 as prior
from experiments.as_safety_v2.transport import TransportError

runtime = prior.runtime
ROOT = runtime.baseline.ROOT
PREFIX = "as-safety-eb-source-position-v22"
PROTOCOL = runtime.baseline.DATA / f"{PREFIX}-protocol.json"
JOURNAL = runtime.baseline.DATA / f"{PREFIX}-journal.v1.jsonl"
PRIVATE_DIR = Path("/private/tmp") / f"{PREFIX}-raw"
SOURCES = (
    "experiments/as_safety_atomic_edges_v22.py",
    "docs/portfolio/nlu_safety_eb_source_position_v22_method.md",
)
PRIOR_JOURNAL_SHA = "710853bad7c0871277d4ebbf11c0196bd965bc8bc87110437a339a9a96567fff"


def move_event(pair, messages):
    lines = messages[1]["content"].splitlines()
    if pair.event["clause_index"] != 2 or lines[1:3] != [
        f"2. {pair.clauses[0]}",
        f"1. {pair.clauses[1]}",
    ]:
        raise ValueError("unexpected baseline row order")
    lines[1], lines[2] = lines[2], lines[1]
    return [messages[0], {**messages[1], "content": "\n".join(lines)}]


def requests():
    policy, old, previous = prior.requests()
    prior_sha = prior.verified_protocol(old, previous)
    if prior.sha(prior.JOURNAL.read_bytes()) != PRIOR_JOURNAL_SHA:
        raise ValueError("baseline journal differs")
    calls = {}
    for name, (pair, messages, schema, _) in old.items():
        moved = move_event(pair, messages)
        calls[name] = (
            pair,
            moved,
            schema,
            runtime.v4.request_bytes(moved, schema, policy, "variant"),
        )
    return policy, calls, prior_sha


def manifest(commit, calls, prior_sha):
    sources = {path: prior.sha(prior.git("show", f"{commit}:{path}")) for path in SOURCES}
    if any(prior.sha((ROOT / path).read_bytes()) != digest for path, digest in sources.items()):
        raise ValueError("frozen sources differ")
    return {
        "commit": commit,
        "source_sha256": sources,
        "v21_protocol_sha256": prior_sha,
        "v21_journal_sha256": PRIOR_JOURNAL_SHA,
        "model_sha256": runtime.MODEL_SHA,
        "image_digest": runtime.v1.IMAGE,
        "order": list(calls),
        "request_sha256": {name: prior.sha(call[3]) for name, call in calls.items()},
    }


def load_protocol(calls, prior_sha):
    raw = PROTOCOL.read_bytes()
    frozen = json.loads(raw, object_pairs_hook=runtime.v4._unique_pairs)
    if frozen != manifest(frozen["commit"], calls, prior_sha):
        raise ValueError("frozen protocol differs")
    if raw != prior.git("show", f"HEAD:{PROTOCOL.relative_to(ROOT)}"):
        raise ValueError("protocol must be committed before calls")
    return prior.sha(raw)


def capture(name, call, policy, attestor):
    pair, messages, schema, body = call
    row = {"call": name, "request_sha256": prior.sha(body), "selected": None}
    try:
        response = runtime.baseline.guarded_call(
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
    raw_sha, raw_bytes = runtime.v1._write_private_raw(
        PRIVATE_DIR / f"{name}.json.txt", response.content
    )
    selected, error = prior.decode(pair, response.finish_reason, response.content)
    return {
        **row,
        "selected": selected,
        "error": error,
        "finish_reason": response.finish_reason,
        "raw_sha256": raw_sha,
        "raw_bytes": raw_bytes,
    }


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
                row = capture(name, call, policy, attestor)
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
        if row["request_sha256"] != prior.sha(body):
            raise ValueError(f"request differs: {name}")
        if "raw_sha256" not in row:
            if not row["error"] or "http_status" not in row:
                raise ValueError(f"missing completion or transport error: {name}")
            continue
        path = PRIVATE_DIR / f"{name}.json.txt"
        if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise ValueError(f"raw response permissions differ: {name}")
        raw = path.read_bytes()
        if (prior.sha(raw), len(raw)) != (row["raw_sha256"], row["raw_bytes"]):
            raise ValueError(f"raw response differs: {name}")
        if prior.decode(pair, row["finish_reason"], raw.decode()) != (
            row["selected"],
            row["error"],
        ):
            raise ValueError(f"outcome differs: {name}")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "replay"))
    parser.add_argument("--model-path", type=Path)
    args = parser.parse_args()
    policy, calls, prior_sha = requests()
    if args.command == "replay":
        print(json.dumps(replay(calls, load_protocol(calls, prior_sha)), indent=2))
        return
    if args.model_path is None:
        parser.error("--model-path is required")
    if JOURNAL.exists() or PRIVATE_DIR.exists():
        raise FileExistsError("existing or partial run requires manual audit")
    runtime.v12._clean()
    if args.command == "run":
        run(args.model_path, policy, calls, load_protocol(calls, prior_sha))
        return
    if runtime.v1.digest_file(args.model_path) != runtime.MODEL_SHA:
        raise ValueError("model digest differs")
    with PROTOCOL.open("x", encoding="utf-8") as stream:
        json.dump(
            manifest(prior.git("rev-parse", "HEAD").decode().strip(), calls, prior_sha),
            stream,
            indent=2,
        )
        stream.write("\n")


if __name__ == "__main__":
    main()
