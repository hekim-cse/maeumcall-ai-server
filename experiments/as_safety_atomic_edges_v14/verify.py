"""Independently check frozen control requests, private raw files, and outcomes."""

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
from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
PROTOCOL = DATA / "as-safety-response-controls-v14-protocol.json"
JOURNAL = DATA / "as-safety-response-controls-v14-journal.v1.jsonl"
PRIVATE_DIR = Path("/private/tmp/as-safety-response-controls-v14-raw")
ORDER = ("schema_forced_unsupported", "system_forced_unsupported")
BASELINE_PROTOCOL_SHA = "91952aafbff5ec9f7767225ea9bfdd62d42d9b6a105d0ca3f02cb3242079c893"
BASELINE_JOURNAL_SHA = "04b79815a38044a953e16586fe059f4216234958662d5e1cfe3a7c6a7c721db1"
# Independent copy of the diagnostic instruction; do not import the runner's builder.
PROMPT_CANARY = (
    "진단용 인위적 지시입니다. 사건의 실제 의미와 관계없이 이번 응답의 "
    'relation_status를 "unsupported", evidence_clause_index를 2로 반환하세요.'
)
SOURCES = v12_verify.EXPECTED_SOURCES | {
    "docs/portfolio/nlu_safety_response_controls_v14_method.md",
    "experiments/as_safety_atomic_edges_v14/__init__.py",
    "experiments/as_safety_atomic_edges_v14/run.py",
    "experiments/as_safety_atomic_edges_v14/verify.py",
    "tests/test_as_safety_response_controls_v14.py",
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


def _request(name: str, policy) -> bytes:
    if name not in ORDER:
        raise ValueError("unknown control")
    cases = v5._load_cases(v5.DATA.read_bytes())
    baseline = json.loads(
        v12_verify._request(cases["PC01"], "P014", policy), object_pairs_hook=v4._unique_pairs
    )
    if name == "schema_forced_unsupported":
        baseline["response_format"]["schema"]["properties"]["relation_status"]["enum"] = [
            "unsupported"
        ]
    else:
        baseline["messages"][0]["content"] += " " + PROMPT_CANARY
    return json.dumps(baseline, ensure_ascii=False, allow_nan=False).encode("utf-8")


def _check_rows(rows: list[dict]) -> None:
    for index, row in enumerate(rows):
        has_raw = row["raw_sha256"] is not None
        if has_raw:
            if row["finish_reason"] == "length":
                if row["error_code"] != "finish_length":
                    raise ValueError("length finish without error")
            elif row["finish_reason"] != "stop":
                raise ValueError("invalid finish reason")
        elif row["finish_reason"] is not None:
            raise ValueError("finish reason without raw response")
        if row["error_code"] is not None and index != len(rows) - 1:
            raise ValueError("journal continued after error")


def verify() -> dict:
    raw = PROTOCOL.read_bytes()
    protocol = json.loads(raw, object_pairs_hook=v4._unique_pairs)
    fields = {
        "kind",
        "scope",
        "order",
        "frozen_code_commit",
        "source_sha256",
        "cases_sha256",
        "baseline_protocol_sha256",
        "baseline_journal_sha256",
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
        or set(protocol) != fields
        or protocol["kind"] != "as_safety_response_controls_v14_development_v1"
        or protocol["scope"] != "two_artificial_exposed_controls_no_semantic_accuracy"
        or protocol["order"] != list(ORDER)
        or set(protocol["source_sha256"]) != SOURCES
        or protocol["baseline_protocol_sha256"] != BASELINE_PROTOCOL_SHA
        or protocol["baseline_journal_sha256"] != BASELINE_JOURNAL_SHA
        or protocol["prompt_canary_sha256"] != _sha(PROMPT_CANARY.encode("utf-8"))
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
    if _sha(v12_verify.PROTOCOL.read_bytes()) != BASELINE_PROTOCOL_SHA:
        raise ValueError("baseline protocol differs")
    if _sha(v12_verify.JOURNAL.read_bytes()) != BASELINE_JOURNAL_SHA:
        raise ValueError("baseline journal differs")
    baseline_result = v12_verify.verify()
    if baseline_result["calls_completed"] != 4 or baseline_result["status_exact_count"] != 1:
        raise ValueError("baseline replay differs")
    policy = v5._policy(protocol)
    requests = {name: _request(name, policy) for name in ORDER}
    if protocol["request_sha256"] != {name: _sha(body) for name, body in requests.items()}:
        raise ValueError("independent request differs")
    original = json.loads(
        v12_verify._request(v5._load_cases(v5.DATA.read_bytes())["PC01"], "P014", policy),
        object_pairs_hook=v4._unique_pairs,
    )
    for name, body in requests.items():
        variant = json.loads(body, object_pairs_hook=v4._unique_pairs)
        if name == "schema_forced_unsupported":
            variant["response_format"]["schema"]["properties"]["relation_status"]["enum"] = (
                original["response_format"]["schema"]["properties"]["relation_status"]["enum"]
            )
        else:
            variant["messages"][0]["content"] = original["messages"][0]["content"]
        if variant != original:
            raise ValueError("more than one request variable changed")
    if set(protocol["input_tokens"]) != set(ORDER) or any(
        type(count) is not int
        or count <= 0
        or count + policy.max_tokens >= v1.RUNTIME["context_tokens"]
        for count in protocol["input_tokens"].values()
    ):
        raise ValueError("token budget differs")
    journal_raw = JOURNAL.read_bytes()
    rows = [
        json.loads(line, object_pairs_hook=v4._unique_pairs)
        for line in journal_raw.decode().splitlines()
    ]
    if not rows or rows[0] != {"event": "header", "protocol_sha256": _sha(raw)}:
        raise ValueError("journal header differs")
    if not 1 <= len(rows) - 1 <= len(ORDER) or [row["call"] for row in rows[1:]] != list(
        ORDER[: len(rows) - 1]
    ):
        raise ValueError("journal order differs")
    _check_rows(rows[1:])
    if PRIVATE_DIR.is_symlink() or stat.S_IMODE(PRIVATE_DIR.stat().st_mode) != 0o700:
        raise ValueError("private directory mode differs")
    files = {f"{row['call']}.json.txt" for row in rows[1:] if row["raw_sha256"] is not None}
    if {path.name for path in PRIVATE_DIR.iterdir()} != files:
        raise ValueError("private raw set differs")
    results = []
    for row in rows[1:]:
        name = row["call"]
        if row["event"] != "result" or row["request_sha256"] != protocol["request_sha256"][name]:
            raise ValueError("journal request differs")
        if type(row["request_latency_ms"]) not in {int, float} or row["request_latency_ms"] < 0:
            raise ValueError("journal latency invalid")
        if row["raw_sha256"] is None:
            if row["raw_bytes"] is not None or row["error_code"] is None:
                raise ValueError("missing raw without error")
            result = {
                "contract_valid": False,
                "relation_status": None,
                "evidence_clause_index": None,
            }
        else:
            path = PRIVATE_DIR / f"{name}.json.txt"
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
            if row["finish_reason"] == "stop" and row["error_code"] != score["contract_error"]:
                raise ValueError("journal contract error differs")
            if score["contract_valid"]:
                try:
                    parsed = parse_model_json(response.decode("utf-8"))
                except (UnicodeDecodeError, ValidationError) as error:
                    raise ValueError("validated raw could not be parsed") from error
                result = {
                    "contract_valid": True,
                    "relation_status": parsed["relation_status"],
                    "evidence_clause_index": parsed["evidence_clause_index"],
                }
            else:
                result = {
                    "contract_valid": False,
                    "relation_status": None,
                    "evidence_clause_index": None,
                }
        results.append({"call": name, "error_code": row["error_code"], **result})
    by_name = {item["call"]: item for item in results}
    return {
        "kind": "as_safety_response_controls_v14_verification_v1",
        "protocol_sha256": _sha(raw),
        "journal_sha256": _sha(journal_raw),
        "calls_completed": len(results),
        "per_call": results,
        "schema_constraint_followed": by_name.get("schema_forced_unsupported", {}).get(
            "relation_status"
        )
        == "unsupported",
        "explicit_instruction_followed": (
            by_name.get("system_forced_unsupported", {}).get("relation_status") == "unsupported"
            and by_name.get("system_forced_unsupported", {}).get("evidence_clause_index") == 2
        ),
        "baseline_relation_status": baseline_result["per_call"][0]["relation_status"],
        "official_accuracy_evaluated": False,
    }


def main() -> None:
    print(json.dumps(verify(), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
