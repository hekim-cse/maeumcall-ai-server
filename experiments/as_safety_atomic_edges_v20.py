"""Compare one numbered source question with the frozen three-question run."""

import argparse
import json
import stat
from pathlib import Path

from experiments import as_safety_atomic_edges_v19 as runtime
from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.transport import TransportError

baseline = runtime.baseline
KEY = "source_evidence"
PREFIX = "as-safety-eb-single-source-v20"
PROTOCOL = baseline.DATA / f"{PREFIX}-protocol.json"
JOURNAL = baseline.DATA / f"{PREFIX}-journal.v1.jsonl"
PRIVATE_DIR = Path("/private/tmp") / f"{PREFIX}-raw"
V19_JOURNAL_SHA = "7975154bccfd21d8b5d007f5f7b4fd2fd2ef4abd28adac730afb7e98bb184cbf"
SOURCES = (
    "experiments/as_safety_atomic_edges_v20.py",
    "experiments/as_safety_atomic_edges_v19.py",
    "experiments/as_safety_atomic_edges_v18/run.py",
    "docs/portfolio/nlu_safety_eb_single_source_v20_method.md",
)


def requests():
    policy, original = baseline.calls()
    baseline.load_protocol(original, replay_only=True)
    result = {}
    for name, (pair, messages, schema, _) in original.items():
        if not name.endswith("-forward"):
            continue
        context, _, _, _, _ = messages[1]["content"].rsplit("\n", 4)
        instructions = (
            "근거 문장 번호를 정수로 반환하고 근거가 없으면 null로 두세요. "
            "후보 구절이 등장한다는 이유만으로 출처를 확정하지 마세요."
        )
        context = context.rsplit("\n", 1)[0]
        question = f"{KEY}: {baseline.selection.QUESTIONS[0][1]}"
        single = [
            messages[0],
            {
                "role": "user",
                "content": f"{context}\n{instructions}\n{question}\n{KEY}만 포함한 JSON 객체를 반환하세요.",
            },
        ]
        single_schema = {
            **schema,
            "properties": {KEY: schema["properties"][KEY]},
            "required": [KEY],
        }
        body = runtime.v4.request_bytes(single, single_schema, policy, "variant")
        result[name] = (pair, single, single_schema, body)
    return policy, result


def validate(raw, pair):
    data = parse_model_json(raw)
    if type(data) is not dict or set(data) != {KEY}:
        raise ValidationError("fields_invalid", KEY)
    number = data[KEY]
    if number is not None and (
        type(number) is not int or number not in baseline.selection.candidates(pair)
    ):
        raise ValidationError("evidence_candidate_not_offered", KEY)
    return number


def manifest(commit, calls):
    sha, git = runtime.v12._sha, runtime.v12._git
    hashes = {p: sha(git("show", f"{commit}:{p}")) for p in SOURCES}
    if any(sha((baseline.ROOT / p).read_bytes()) != digest for p, digest in hashes.items()):
        raise ValueError("frozen source differs")
    if sha(runtime.JOURNAL.read_bytes()) != V19_JOURNAL_SHA:
        raise ValueError("baseline journal differs")
    return {
        "commit": commit,
        "source_sha256": hashes,
        "v19_journal_sha256": V19_JOURNAL_SHA,
        "model_sha256": runtime.MODEL_SHA,
        "image_digest": runtime.v1.IMAGE,
        "order": list(calls),
        "request_sha256": {name: sha(call[3]) for name, call in calls.items()},
    }


def capture(name, call, policy, attestor):
    pair, messages, schema, body = call
    row = {"call": name, "request_sha256": runtime.v12._sha(body), "selected": None, "error": None}
    try:
        response = baseline.guarded_call(
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
    row["finish_reason"] = response.finish_reason
    row["raw_sha256"], row["raw_bytes"] = runtime.v1._write_private_raw(
        PRIVATE_DIR / f"{name}.json.txt", response.content
    )
    if response.finish_reason != "stop":
        return {**row, "error": "finish_length"}
    try:
        return {**row, "selected": validate(response.content, pair)}
    except ValidationError as exc:
        return {**row, "error": exc.code}


def load_protocol(calls):
    raw = PROTOCOL.read_bytes()
    frozen = json.loads(raw, object_pairs_hook=runtime.v4._unique_pairs)
    if frozen != manifest(frozen["commit"], calls):
        raise ValueError("protocol differs")
    if runtime.v12._git("show", f"HEAD:{PROTOCOL.relative_to(baseline.ROOT)}") != raw:
        raise ValueError("protocol must be committed before calls")
    return runtime.v12._sha(raw)


def run(model, policy, calls):
    protocol_sha = load_protocol(calls)
    with runtime.server(model) as attestor:
        counts = {
            name: baseline.guarded_call(
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


def replay(calls):
    header, *rows = map(json.loads, JOURNAL.read_text(encoding="utf-8").splitlines())
    if header["protocol_sha256"] != load_protocol(calls):
        raise ValueError("journal protocol differs")
    if [row["call"] for row in rows] != list(calls)[: len(rows)]:
        raise ValueError("journal order differs")
    if (
        not rows
        or any(row["error"] for row in rows[:-1])
        or (len(rows) < len(calls) and rows[-1]["error"] is None)
    ):
        raise ValueError("journal ended inconsistently")
    if PRIVATE_DIR.is_symlink() or stat.S_IMODE(PRIVATE_DIR.stat().st_mode) != 0o700:
        raise ValueError("raw response directory differs")
    for row in rows:
        name = row["call"]
        pair, _, _, body = calls[name]
        if row["request_sha256"] != runtime.v12._sha(body):
            raise ValueError(f"request differs: {name}")
        if "raw_sha256" not in row:
            if not row["error"] or "http_status" not in row:
                raise ValueError(f"missing raw response: {name}")
            continue
        path = PRIVATE_DIR / f"{name}.json.txt"
        raw = path.read_bytes()
        if (
            path.is_symlink()
            or stat.S_IMODE(path.stat().st_mode) != 0o600
            or (runtime.v12._sha(raw), len(raw)) != (row["raw_sha256"], row["raw_bytes"])
        ):
            raise ValueError(f"raw response differs: {name}")
        selected, error = None, None
        if row["finish_reason"] != "stop":
            error = "finish_length"
        else:
            try:
                selected = validate(raw.decode(), pair)
            except ValidationError as exc:
                error = exc.code
        if (selected, error) != (row["selected"], row["error"]):
            raise ValueError(f"score differs: {name}")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "replay"))
    parser.add_argument("--model-path", type=Path)
    args = parser.parse_args()
    policy, calls = requests()
    if args.command == "replay":
        print(json.dumps(replay(calls), indent=2))
        return
    if args.model_path is None:
        parser.error("--model-path is required")
    if JOURNAL.exists() or PRIVATE_DIR.exists():
        raise FileExistsError("existing or partial run requires manual audit")
    runtime.v12._clean()
    if args.command == "run":
        run(args.model_path, policy, calls)
        return
    if runtime.v1.digest_file(args.model_path) != runtime.MODEL_SHA:
        raise ValueError("model digest differs")
    data = manifest(runtime.v12._git("rev-parse", "HEAD").decode().strip(), calls)
    with PROTOCOL.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
