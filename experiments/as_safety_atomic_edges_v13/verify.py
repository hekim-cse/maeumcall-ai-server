"""Independently replay the v13 criterion requests and restricted responses."""

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
from experiments.as_safety_v2.quotes import split_clauses

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
PROTOCOL = DATA / "as-safety-eb-criteria-v13-development-protocol.json"
JOURNAL = DATA / "as-safety-eb-criteria-v13-development-journal.v1.jsonl"
PRIVATE_DIR = Path("/private/tmp/as-safety-eb-criteria-v13-raw")
ORDER = ("PC01-P014", "PC01-P016", "NC01-P020", "NC01-P002")
BASELINE_PROTOCOL_SHA = "91952aafbff5ec9f7767225ea9bfdd62d42d9b6a105d0ca3f02cb3242079c893"
BASELINE_JOURNAL_SHA = "04b79815a38044a953e16586fe059f4216234958662d5e1cfe3a7c6a7c721db1"
# Intentionally duplicated: do not use the runner to reconstruct the prompt.
CRITERION = (
    "판정할 때 후보 구절 전체를 기준으로 삼으세요. 후보 구절에 위험 현상이나 동작이 "
    "섞여 있어 전체가 물리적 출처를 가리키지 않으면 unsupported입니다. 물체나 부위인 "
    "후보라도 이 사건의 출처라는 연결이 원문에서 확인되지 않으면 insufficient입니다."
)
SOURCES = v12_verify.EXPECTED_SOURCES | {
    "docs/portfolio/nlu_safety_eb_criteria_v13_method.md",
    "experiments/as_safety_atomic_edges_v13/__init__.py",
    "experiments/as_safety_atomic_edges_v13/run.py",
    "experiments/as_safety_atomic_edges_v13/verify.py",
    "tests/test_as_safety_criteria_v13.py",
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _request(case: dict, candidate_id: str, policy) -> bytes:
    original = json.loads(
        v12_verify._request(case, candidate_id, policy), object_pairs_hook=v4._unique_pairs
    )
    messages = original["messages"]
    if len(messages) != 2 or messages[0]["role"] != "system":
        raise ValueError("baseline request shape differs")
    messages[0]["content"] += " " + CRITERION
    return json.dumps(original, ensure_ascii=False, allow_nan=False).encode("utf-8")


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
    fields = {
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
        or set(protocol) != fields
        or protocol["kind"] != "as_safety_eb_criteria_v13_development_v1"
        or protocol["scope"]
        != "four_exposed_user_reviewed_pairs_single_prompt_change_development_only"
        or protocol["order"] != list(ORDER)
        or set(protocol["source_sha256"]) != SOURCES
        or protocol["criterion_sha256"] != _sha(CRITERION.encode("utf-8"))
        or protocol["baseline_protocol_sha256"] != BASELINE_PROTOCOL_SHA
        or protocol["baseline_journal_sha256"] != BASELINE_JOURNAL_SHA
        or protocol["model_sha256"] != v1.MODEL_SHA
        or protocol["image_digest"] != v1.IMAGE
        or protocol["container_name"] != v10_run.CONTAINER
        or protocol["request_policy"] != v1.REQUEST_POLICY
        or protocol["retry_policy"] != v1.RETRY_POLICY
        or protocol["server_args"] != list(v1.SERVER_ARGS)
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
    baseline = v12_verify.verify()
    if (
        _sha(json.dumps(baseline, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        != protocol["baseline_verification_sha256"]
    ):
        raise ValueError("baseline verification differs")
    cases = v5._load_cases(v5.DATA.read_bytes())
    policy = v5._policy(protocol)
    requests = {
        name: _request(cases[name.split("-", 1)[0]], name.split("-", 1)[1], policy)
        for name in ORDER
    }
    if protocol["request_sha256"] != {name: _sha(body) for name, body in requests.items()}:
        raise ValueError("independent request differs")
    old = json.loads(v12_verify.PROTOCOL.read_bytes(), object_pairs_hook=v4._unique_pairs)
    for name, body in requests.items():
        if _sha(body) == old["request_sha256"][name]:
            raise ValueError("request did not change")
        current_payload = json.loads(body, object_pairs_hook=v4._unique_pairs)
        old_payload = json.loads(
            v12_verify._request(cases[name.split("-", 1)[0]], name.split("-", 1)[1], policy),
            object_pairs_hook=v4._unique_pairs,
        )
        current_payload["messages"][0]["content"] = old_payload["messages"][0]["content"]
        if current_payload != old_payload:
            raise ValueError("more than one request variable changed")
    if set(protocol["input_tokens"]) != set(ORDER) or any(
        type(count) is not int
        or count <= 0
        or count + policy.max_tokens >= v1.RUNTIME["context_tokens"]
        for count in protocol["input_tokens"].values()
    ):
        raise ValueError("input token budget differs")
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
    if any(row["error_code"] is not None for row in rows[1:-1]):
        raise ValueError("journal continued after error")
    if PRIVATE_DIR.is_symlink() or stat.S_IMODE(PRIVATE_DIR.stat().st_mode) != 0o700:
        raise ValueError("private directory mode differs")
    expected_files = {
        f"{row['call']}.json.txt" for row in rows[1:] if row["raw_sha256"] is not None
    }
    if {path.name for path in PRIVATE_DIR.iterdir()} != expected_files:
        raise ValueError("private raw file set differs")
    reviewed = json.loads(v12_verify.LABELS.read_bytes(), object_pairs_hook=v4._unique_pairs)
    if reviewed["kind"] != "as_safety_eb_pair_v12_user_reviewed_development_labels" or [
        item["call"] for item in reviewed["cases"]
    ] != list(ORDER):
        raise ValueError("reviewed label identity differs")
    labels = {item["call"]: item for item in reviewed["cases"]}
    results = []
    for row in rows[1:]:
        name = row["call"]
        if row["event"] != "result" or row["request_sha256"] != protocol["request_sha256"][name]:
            raise ValueError("journal request differs")
        if type(row["request_latency_ms"]) not in {int, float} or row["request_latency_ms"] < 0:
            raise ValueError("journal latency invalid")
        if row["raw_sha256"] is None:
            if row["raw_bytes"] is not None or row["error_code"] is None:
                raise ValueError("missing raw response without error")
            score = {
                "contract_valid": False,
                "contract_error": row["error_code"],
                "relation_status": None,
                "status_exact": None,
                "evidence_clause_exact": None,
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
                    response,
                    len(split_clauses(cases[name.split("-", 1)[0]]["user_message"])),
                    labels[name],
                )
                if row["finish_reason"] == "stop"
                else {
                    "contract_valid": False,
                    "contract_error": row["error_code"] or "finish_length",
                    "relation_status": None,
                    "status_exact": None,
                    "evidence_clause_exact": None,
                }
            )
            if row["finish_reason"] == "stop" and row["error_code"] != score["contract_error"]:
                raise ValueError("journal contract error differs")
        results.append({"call": name, "error_code": row["error_code"], **score})
    gate = len(results) == len(ORDER) and all(
        item["error_code"] is None
        and item["contract_valid"]
        and item["status_exact"] is True
        and item["evidence_clause_exact"] is True
        for item in results
    )
    return {
        "kind": "as_safety_eb_criteria_v13_development_verification_v1",
        "protocol_sha256": _sha(raw),
        "journal_sha256": _sha(journal_raw),
        "calls_completed": len(results),
        "contract_pass_count": sum(item["contract_valid"] for item in results),
        "status_exact_count": sum(item["status_exact"] is True for item in results),
        "evidence_clause_exact_count": sum(
            item["evidence_clause_exact"] is True for item in results
        ),
        "baseline_status_exact_count": baseline["status_exact_count"],
        "baseline_evidence_clause_exact_count": baseline["evidence_clause_exact_count"],
        "per_call": results,
        "pair_gate_pass": gate,
        "official_accuracy_evaluated": False,
    }


def main() -> None:
    print(json.dumps(verify(), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
