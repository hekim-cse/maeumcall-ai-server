"""Freeze and run a four-pair, single-prompt-change development contrast."""

from __future__ import annotations

import argparse
import hashlib
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
from experiments.as_safety_atomic_edges_v12 import verify as v12_verify
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.transport import TransportError

ROOT = v12.ROOT
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
PROTOCOL = DATA / "as-safety-eb-criteria-v13-development-protocol.json"
JOURNAL = DATA / "as-safety-eb-criteria-v13-development-journal.v1.jsonl"
PRIVATE_DIR = Path("/private/tmp/as-safety-eb-criteria-v13-raw")
ORDER = v12.ORDER
KIND = "as_safety_eb_criteria_v13_development_v1"
BASELINE_PROTOCOL_SHA = "91952aafbff5ec9f7767225ea9bfdd62d42d9b6a105d0ca3f02cb3242079c893"
BASELINE_JOURNAL_SHA = "04b79815a38044a953e16586fe059f4216234958662d5e1cfe3a7c6a7c721db1"
# One added instruction. The candidate, event, response schema, and request policy stay fixed.
CRITERION = (
    "판정할 때 후보 구절 전체를 기준으로 삼으세요. 후보 구절에 위험 현상이나 동작이 "
    "섞여 있어 전체가 물리적 출처를 가리키지 않으면 unsupported입니다. 물체나 부위인 "
    "후보라도 이 사건의 출처라는 연결이 원문에서 확인되지 않으면 insufficient입니다."
)
SOURCES = tuple(
    sorted(
        set(v12.SOURCES)
        | {
            "docs/portfolio/nlu_safety_eb_criteria_v13_method.md",
            "experiments/as_safety_atomic_edges_v13/__init__.py",
            "experiments/as_safety_atomic_edges_v13/run.py",
            "experiments/as_safety_atomic_edges_v13/verify.py",
            "tests/test_as_safety_criteria_v13.py",
        }
    )
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _baseline_guard() -> dict:
    if _sha(v12.PROTOCOL.read_bytes()) != BASELINE_PROTOCOL_SHA:
        raise ValueError("baseline protocol differs")
    if _sha(v12.JOURNAL.read_bytes()) != BASELINE_JOURNAL_SHA:
        raise ValueError("baseline journal differs")
    result = v12_verify.verify()
    if (
        result["calls_completed"] != 4
        or result["contract_pass_count"] != 4
        or result["status_exact_count"] != 1
        or result["evidence_clause_exact_count"] != 3
        or result["pair_gate_pass"] is not False
    ):
        raise ValueError("baseline replay differs")
    return result


def messages(pair: pair_contract.FixedPair) -> list[dict[str, str]]:
    original = pair_contract.messages(pair)
    return [
        {"role": "system", "content": original[0]["content"] + " " + CRITERION},
        original[1],
    ]


def _requests(cases: dict, policy) -> dict[str, bytes]:
    result = {}
    for case_id, candidate_id in ORDER:
        pair = pair_contract.fixed_pair(cases[case_id], candidate_id, v12._kiwi())
        result[v12._pair_name(case_id, candidate_id)] = v4.request_bytes(
            messages(pair), pair_contract.schema(pair), policy, "variant"
        )
    return result


def prepare(model_path: Path) -> None:
    if PROTOCOL.exists() or JOURNAL.exists() or PRIVATE_DIR.exists():
        raise FileExistsError("existing or partial probe requires manual audit")
    v12._clean()
    baseline = _baseline_guard()
    commit = v12._git("rev-parse", "HEAD").decode().strip()
    cases = probe.cases()
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    requests = _requests(cases, policy)
    historical = json.loads(v12.PROTOCOL.read_bytes(), object_pairs_hook=v4._unique_pairs)
    if set(requests) != set(historical["request_sha256"]) or any(
        _sha(body) == historical["request_sha256"][name] for name, body in requests.items()
    ):
        raise ValueError("criterion request did not change every pair")
    with v12.v10_run._server(model_path) as attestor:
        tokens = {
            name: guarded_call(attestor, lambda body=body: v7._tokenize_request(body))
            for name, body in requests.items()
        }
    if any(count + policy.max_tokens >= v1.RUNTIME["context_tokens"] for count in tokens.values()):
        raise ValueError("request exceeds context")
    sources = {path: _sha(v12._git("show", f"{commit}:{path}")) for path in SOURCES}
    if sources != {path: _sha((ROOT / path).read_bytes()) for path in SOURCES}:
        raise ValueError("source differs from committed code")
    payload = {
        "kind": KIND,
        "scope": "four_exposed_user_reviewed_pairs_single_prompt_change_development_only",
        "order": [v12._pair_name(*item) for item in ORDER],
        "frozen_code_commit": commit,
        "source_sha256": sources,
        "cases_sha256": _sha(v5.DATA.read_bytes()),
        "baseline_protocol_sha256": BASELINE_PROTOCOL_SHA,
        "baseline_journal_sha256": BASELINE_JOURNAL_SHA,
        "baseline_verification_sha256": _sha(
            json.dumps(baseline, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ),
        "criterion_sha256": _sha(CRITERION.encode("utf-8")),
        "model_sha256": v1.MODEL_SHA,
        "image_digest": v1.IMAGE,
        "container_name": v12.v10_run.CONTAINER,
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
    required = {
        "kind",
        "scope",
        "order",
        "frozen_code_commit",
        "source_sha256",
        "cases_sha256",
        "baseline_protocol_sha256",
        "baseline_journal_sha256",
        "baseline_verification_sha256",
        "criterion_sha256",
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
        or set(protocol) != required
        or protocol["kind"] != KIND
        or protocol["scope"]
        != "four_exposed_user_reviewed_pairs_single_prompt_change_development_only"
        or protocol["order"] != [v12._pair_name(*item) for item in ORDER]
        or protocol["baseline_protocol_sha256"] != BASELINE_PROTOCOL_SHA
        or protocol["baseline_journal_sha256"] != BASELINE_JOURNAL_SHA
        or protocol["criterion_sha256"] != _sha(CRITERION.encode("utf-8"))
        or protocol["model_sha256"] != v1.MODEL_SHA
        or protocol["image_digest"] != v1.IMAGE
        or protocol["container_name"] != v12.v10_run.CONTAINER
        or protocol["server_args"] != list(v1.SERVER_ARGS)
        or protocol["request_policy"] != v1.REQUEST_POLICY
        or protocol["retry_policy"] != v1.RETRY_POLICY
        or protocol["max_context_tokens"] != v1.RUNTIME["context_tokens"]
        or protocol["journal"] != JOURNAL.relative_to(ROOT).as_posix()
        or protocol["private_output"] != "outside_repository_mode_0700_files_0600"
        or set(protocol["source_sha256"]) != set(SOURCES)
    ):
        raise ValueError("protocol identity differs")
    baseline = _baseline_guard()
    if protocol["baseline_verification_sha256"] != _sha(
        json.dumps(baseline, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ):
        raise ValueError("baseline verification differs")
    commit = protocol["frozen_code_commit"]
    for path, digest in protocol["source_sha256"].items():
        if digest != _sha(v12._git("show", f"{commit}:{path}")) or digest != _sha(
            (ROOT / path).read_bytes()
        ):
            raise ValueError("frozen source differs")
    if protocol["cases_sha256"] != _sha(v5.DATA.read_bytes()):
        raise ValueError("case source differs")
    cases = probe.cases()
    policy = v5._policy(protocol)
    requests = _requests(cases, policy)
    if protocol["request_sha256"] != {name: _sha(body) for name, body in requests.items()}:
        raise ValueError("frozen request differs")
    if set(protocol["input_tokens"]) != set(requests) or any(
        type(count) is not int
        or count <= 0
        or count + policy.max_tokens >= v1.RUNTIME["context_tokens"]
        for count in protocol["input_tokens"].values()
    ):
        raise ValueError("frozen token budget differs")
    if v12._git("show", f"HEAD:{PROTOCOL.relative_to(ROOT).as_posix()}") != raw:
        raise ValueError("protocol must be committed before calls")
    v12._clean()
    return protocol, _sha(raw), cases, policy, requests


def run(model_path: Path) -> None:
    if JOURNAL.exists() or PRIVATE_DIR.exists():
        raise FileExistsError("existing or partial run requires manual audit")
    protocol, protocol_sha, cases, policy, requests = _load_protocol()
    with v12.v10_run._server(model_path) as attestor:
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
                name = v12._pair_name(case_id, candidate_id)
                pair = pair_contract.fixed_pair(cases[case_id], candidate_id, v12._kiwi())
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
                            messages(pair),
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
                    else:
                        try:
                            pair_contract.validate_response(completion.content, pair)
                        except ValidationError as error:
                            row["error_code"] = error.code
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
