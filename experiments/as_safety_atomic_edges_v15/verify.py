"""Independently replay the single v15 prompt-control request and raw response."""

from __future__ import annotations

import hashlib
import json
import stat
import subprocess
from pathlib import Path

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v4 import run as v4
from experiments.as_safety_atomic_edges_v5 import run as v5
from experiments.as_safety_atomic_edges_v10 import run as v10_run
from experiments.as_safety_atomic_edges_v12 import verify as v12_verify
from experiments.as_safety_atomic_edges_v14 import verify as v14_verify

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
PROTOCOL = DATA / "as-safety-system-control-v15-protocol.json"
JOURNAL = DATA / "as-safety-system-control-v15-journal.v1.jsonl"
PRIVATE_DIR = Path("/private/tmp/as-safety-system-control-v15-raw")
CALL = "system_forced_unsupported"
V14_PROTOCOL_SHA = "389f54d5efdde788bc95d4b5b7b2b96474363b15fa8a38d9fd05af34c4b57001"
V14_JOURNAL_SHA = "9b56ed175df2f8acfdbcc518ea2f47a78c11ce081a0d6590e5661acd8fadd020"
SOURCES = v14_verify.SOURCES | {
    "docs/portfolio/nlu_safety_system_control_v15_method.md",
    "experiments/as_safety_atomic_edges_v15/__init__.py",
    "experiments/as_safety_atomic_edges_v15/run.py",
    "experiments/as_safety_atomic_edges_v15/verify.py",
    "tests/test_as_safety_system_control_v15.py",
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _frozen(commit: str, relative: str) -> bytes:
    if (
        type(commit) is not str
        or len(commit) != 40
        or any(char not in "0123456789abcdef" for char in commit)
        or relative.startswith("/")
        or ".." in Path(relative).parts
    ):
        raise ValueError("frozen source reference invalid")
    return subprocess.run(
        ("git", "show", f"{commit}:{relative}"), cwd=ROOT, check=True, capture_output=True
    ).stdout


def verify() -> dict:
    raw = PROTOCOL.read_bytes()
    protocol = json.loads(raw, object_pairs_hook=v4._unique_pairs)
    expected = {
        "kind",
        "scope",
        "call",
        "frozen_code_commit",
        "source_sha256",
        "cases_sha256",
        "v14_protocol_sha256",
        "v14_journal_sha256",
        "prompt_canary_sha256",
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
        or set(protocol) != expected
        or protocol["kind"] != "as_safety_system_control_v15_development_v1"
        or protocol["scope"] != "one_artificial_exposed_system_prompt_control_no_semantic_accuracy"
        or protocol["call"] != CALL
        or set(protocol["source_sha256"]) != SOURCES
        or protocol["v14_protocol_sha256"] != V14_PROTOCOL_SHA
        or protocol["v14_journal_sha256"] != V14_JOURNAL_SHA
        or protocol["prompt_canary_sha256"] != _sha(v14_verify.PROMPT_CANARY.encode("utf-8"))
        or protocol["model_sha256"] != v1.MODEL_SHA
        or protocol["image_digest"] != v1.IMAGE
        or protocol["container_name"] != v10_run.CONTAINER
        or protocol["server_args"] != list(v1.SERVER_ARGS)
        or protocol["request_policy"] != v1.REQUEST_POLICY
        or protocol["retry_policy"] != v1.RETRY_POLICY
        or protocol["max_context_tokens"] != v1.RUNTIME["context_tokens"]
        or protocol["journal"] != JOURNAL.relative_to(ROOT).as_posix()
        or protocol["private_output"] != "outside_repository_mode_0700_files_0600"
    ):
        raise ValueError("protocol identity differs")
    current = (
        subprocess.run(("git", "rev-parse", "HEAD"), cwd=ROOT, check=True, capture_output=True)
        .stdout.decode()
        .strip()
    )
    if _frozen(current, PROTOCOL.relative_to(ROOT).as_posix()) != raw:
        raise ValueError("protocol not committed")
    for path, digest in protocol["source_sha256"].items():
        if _sha(_frozen(protocol["frozen_code_commit"], path)) != digest:
            raise ValueError("frozen source differs")
        if _sha((ROOT / path).read_bytes()) != digest:
            raise ValueError("current source differs from frozen code")
    if _sha(v5.DATA.read_bytes()) != protocol["cases_sha256"]:
        raise ValueError("case source differs")
    if _sha(v14_verify.PROTOCOL.read_bytes()) != V14_PROTOCOL_SHA:
        raise ValueError("v14 protocol differs")
    if _sha(v14_verify.JOURNAL.read_bytes()) != V14_JOURNAL_SHA:
        raise ValueError("v14 journal differs")
    prior = v14_verify.verify()
    if prior["calls_completed"] != 1 or prior["schema_enum_observed"] is not True:
        raise ValueError("v14 partial replay differs")
    policy = v5._policy(protocol)
    request = v14_verify._request(CALL, policy)
    if _sha(request) != protocol["request_sha256"]:
        raise ValueError("independent request differs")
    original = json.loads(
        v12_verify._request(v5._load_cases(v5.DATA.read_bytes())["PC01"], "P014", policy),
        object_pairs_hook=v4._unique_pairs,
    )
    variant = json.loads(request, object_pairs_hook=v4._unique_pairs)
    if (
        variant["messages"][0]["content"]
        != original["messages"][0]["content"] + " " + v14_verify.PROMPT_CANARY
    ):
        raise ValueError("system instruction differs")
    variant["messages"][0]["content"] = original["messages"][0]["content"]
    if variant != original:
        raise ValueError("more than one request variable changed")
    if (
        type(protocol["input_tokens"]) is not int
        or protocol["input_tokens"] <= 0
        or protocol["input_tokens"] + policy.max_tokens >= v1.RUNTIME["context_tokens"]
    ):
        raise ValueError("token budget differs")
    journal_raw = JOURNAL.read_bytes()
    rows = [
        json.loads(line, object_pairs_hook=v4._unique_pairs)
        for line in journal_raw.decode().splitlines()
    ]
    if len(rows) != 2 or rows[0] != {"event": "header", "protocol_sha256": _sha(raw)}:
        raise ValueError("journal header or count differs")
    row = rows[1]
    if (
        row["event"] != "result"
        or row["call"] != CALL
        or row["request_sha256"] != protocol["request_sha256"]
    ):
        raise ValueError("journal call differs")
    v14_verify._check_rows([row])
    if type(row["request_latency_ms"]) not in {int, float} or row["request_latency_ms"] < 0:
        raise ValueError("journal latency invalid")
    if PRIVATE_DIR.is_symlink() or stat.S_IMODE(PRIVATE_DIR.stat().st_mode) != 0o700:
        raise ValueError("private directory mode differs")
    expected_files = {f"{CALL}.json.txt"} if row["raw_sha256"] is not None else set()
    if {path.name for path in PRIVATE_DIR.iterdir()} != expected_files:
        raise ValueError("private raw set differs")
    if row["raw_sha256"] is None:
        if row["raw_bytes"] is not None or row["error_code"] is None:
            raise ValueError("missing raw without error")
        observed_status, observed_index = None, None
        contract_valid = False
    else:
        path = PRIVATE_DIR / f"{CALL}.json.txt"
        if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise ValueError("private raw mode differs")
        response = path.read_bytes()
        if _sha(response) != row["raw_sha256"] or len(response) != row["raw_bytes"]:
            raise ValueError("private raw digest differs")
        score = (
            v12_verify._score(
                response, 2, {"relation_status": "unsupported", "evidence_clause_index": 2}
            )
            if row["finish_reason"] == "stop"
            else {"contract_valid": False, "contract_error": "finish_length"}
        )
        if row["error_code"] != score["contract_error"]:
            raise ValueError("journal contract error differs")
        contract_valid = score["contract_valid"]
        observed_status, observed_index = v14_verify._observed_fields(response)
    return {
        "kind": "as_safety_system_control_v15_verification_v1",
        "protocol_sha256": _sha(raw),
        "journal_sha256": _sha(journal_raw),
        "calls_completed": 1,
        "error_code": row["error_code"],
        "contract_valid": contract_valid,
        "observed_relation_status": observed_status,
        "observed_evidence_clause_index": observed_index,
        "explicit_instruction_followed": contract_valid
        and observed_status == "unsupported"
        and observed_index == 2,
        "official_accuracy_evaluated": False,
    }


def main() -> None:
    print(json.dumps(verify(), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
