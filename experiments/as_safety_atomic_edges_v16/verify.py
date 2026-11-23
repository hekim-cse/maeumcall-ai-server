"""Independently reconstruct v16 requests and replay restricted raw responses."""

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
PROTOCOL = DATA / "as-safety-label-order-v16-development-protocol.json"
JOURNAL = DATA / "as-safety-label-order-v16-development-journal.v1.jsonl"
PRIVATE_DIR = Path("/private/tmp/as-safety-label-order-v16-raw")
ORDER = ("PC01-P014", "PC01-P016", "NC01-P020", "NC01-P002")
BASELINE_PROTOCOL_SHA = "91952aafbff5ec9f7767225ea9bfdd62d42d9b6a105d0ca3f02cb3242079c893"
BASELINE_JOURNAL_SHA = "04b79815a38044a953e16586fe059f4216234958662d5e1cfe3a7c6a7c721db1"
# Duplicated deliberately: the verifier must not import the runner's intervention.
OLD_OPTIONS = (
    "relation_status는 supported(원문이 이 후보를 사건의 물리적 출처로 뒷받침함), "
    "unsupported(이 후보는 현상 자체이거나 원문과 모순되어 출처가 될 수 없음), "
    "insufficient(가능성은 있으나 원문만으로 출처를 확정할 수 없음) 중 하나입니다."
)
NEW_OPTIONS = (
    "relation_status는 insufficient(가능성은 있으나 원문만으로 출처를 확정할 수 없음), "
    "unsupported(이 후보는 현상 자체이거나 원문과 모순되어 출처가 될 수 없음), "
    "supported(원문이 이 후보를 사건의 물리적 출처로 뒷받침함) 중 하나입니다."
)
SOURCES = v12_verify.EXPECTED_SOURCES | {
    "docs/portfolio/nlu_safety_label_order_v16_method.md",
    "experiments/as_safety_atomic_edges_v16/__init__.py",
    "experiments/as_safety_atomic_edges_v16/variant.py",
    "experiments/as_safety_atomic_edges_v16/run.py",
    "experiments/as_safety_atomic_edges_v16/verify.py",
    "tests/test_as_safety_label_order_v16.py",
}
POSTRUN_REVIEW_FILES = frozenset(
    {
        "docs/portfolio/nlu_safety_label_order_v16_method.md",
        "experiments/as_safety_atomic_edges_v16/verify.py",
    }
)
FIELDS = {
    "kind",
    "scope",
    "order",
    "frozen_code_commit",
    "source_sha256",
    "cases_sha256",
    "baseline_protocol_sha256",
    "baseline_journal_sha256",
    "baseline_verification_sha256",
    "original_options_sha256",
    "reversed_options_sha256",
    "model_sha256",
    "image_digest",
    "container_name",
    "server_args",
    "request_policy",
    "retry_policy",
    "request_sha256",
    "max_context_tokens",
    "journal",
    "private_output",
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
        raise ValueError("invalid frozen reference")
    return subprocess.run(
        ("git", "show", f"{commit}:{relative}"), cwd=ROOT, check=True, capture_output=True
    ).stdout


def _request(case: dict, candidate_id: str, policy) -> tuple[bytes, bytes]:
    old = v12_verify._request(case, candidate_id, policy)
    payload = json.loads(old, object_pairs_hook=v4._unique_pairs)
    message = payload["messages"][1]
    if message["role"] != "user" or message["content"].count(OLD_OPTIONS) != 1:
        raise ValueError("baseline prompt differs")
    message["content"] = message["content"].replace(OLD_OPTIONS, NEW_OPTIONS)
    return old, json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()


def _identity(protocol: dict, baseline: dict, baseline_protocol: dict) -> None:
    if (
        type(protocol) is not dict
        or set(protocol) != FIELDS
        or protocol["kind"] != "as_safety_label_order_v16_development_v1"
        or protocol["scope"] != "four_exposed_user_reviewed_pairs_single_label_order_change"
        or protocol["order"] != list(ORDER)
        or set(protocol["source_sha256"]) != SOURCES
        or protocol["cases_sha256"] != _sha(v5.DATA.read_bytes())
        or protocol["baseline_protocol_sha256"] != BASELINE_PROTOCOL_SHA
        or protocol["baseline_journal_sha256"] != BASELINE_JOURNAL_SHA
        or protocol["baseline_verification_sha256"]
        != _sha(json.dumps(baseline, ensure_ascii=False, sort_keys=True).encode())
        or protocol["original_options_sha256"] != _sha(OLD_OPTIONS.encode())
        or protocol["reversed_options_sha256"] != _sha(NEW_OPTIONS.encode())
        or protocol["model_sha256"] != v1.MODEL_SHA
        or protocol["image_digest"] != v1.IMAGE
        or protocol["container_name"] != v10_run.CONTAINER
        or protocol["server_args"] != list(v1.SERVER_ARGS)
        or protocol["request_policy"] != v1.REQUEST_POLICY
        or protocol["retry_policy"] != v1.RETRY_POLICY
        or protocol["max_context_tokens"] != v1.RUNTIME["context_tokens"]
        or protocol["journal"] != JOURNAL.relative_to(ROOT).as_posix()
        or protocol["private_output"] != v1.PRIVATE_OUTPUT
        or set(protocol["request_sha256"]) != set(ORDER)
        or set(baseline_protocol["request_sha256"]) != set(ORDER)
    ):
        raise ValueError("protocol identity differs")


def _rows(rows: list[dict], protocol_sha: str, protocol: dict) -> dict:
    if (
        not rows
        or rows[0].get("event") != "header"
        or rows[0].get("protocol_sha256") != protocol_sha
    ):
        raise ValueError("journal header differs")
    counts = rows[0].get("input_tokens")
    if (
        set(rows[0]) != {"event", "protocol_sha256", "input_tokens"}
        or type(counts) is not dict
        or set(counts) != set(ORDER)
        or any(
            type(count) is not int
            or count <= 0
            or count + protocol["request_policy"]["max_tokens"] >= protocol["max_context_tokens"]
            for count in counts.values()
        )
    ):
        raise ValueError("input token preflight differs")
    result_rows = rows[1:]
    if not 1 <= len(result_rows) <= len(ORDER) or [row.get("call") for row in result_rows] != list(
        ORDER[: len(result_rows)]
    ):
        raise ValueError("journal order differs")
    for index, row in enumerate(result_rows):
        if (
            type(row) is not dict
            or set(row)
            != {
                "event",
                "call",
                "request_sha256",
                "finish_reason",
                "error_code",
                "http_status",
                "raw_sha256",
                "raw_bytes",
                "request_latency_ms",
            }
            or row["event"] != "result"
            or row["request_sha256"] != protocol["request_sha256"][row["call"]]
        ):
            raise ValueError("journal result shape differs")
        if type(row["request_latency_ms"]) not in {int, float} or row["request_latency_ms"] < 0:
            raise ValueError("latency differs")
        if row["raw_sha256"] is None:
            if (
                row["finish_reason"] is not None
                or row["raw_bytes"] is not None
                or row["error_code"] is None
            ):
                raise ValueError("missing response without transport error")
            if row["http_status"] is not None and (
                type(row["http_status"]) is not int or not 100 <= row["http_status"] <= 599
            ):
                raise ValueError("http status differs")
        elif row["finish_reason"] == "length":
            if (
                type(row["raw_sha256"]) is not str
                or len(row["raw_sha256"]) != 64
                or any(char not in "0123456789abcdef" for char in row["raw_sha256"])
                or type(row["raw_bytes"]) is not int
                or row["raw_bytes"] <= 0
                or row["http_status"] is not None
            ):
                raise ValueError("raw response metadata differs")
            if row["error_code"] != "finish_length":
                raise ValueError("length finish differs")
        elif row["finish_reason"] != "stop":
            raise ValueError("response finish differs")
        elif (
            type(row["raw_sha256"]) is not str
            or len(row["raw_sha256"]) != 64
            or any(char not in "0123456789abcdef" for char in row["raw_sha256"])
            or type(row["raw_bytes"]) is not int
            or row["raw_bytes"] <= 0
            or row["http_status"] is not None
        ):
            raise ValueError("raw response metadata differs")
        if row["error_code"] is not None and index != len(result_rows) - 1:
            raise ValueError("journal continued after error")
    return counts


def verify() -> dict:
    raw = PROTOCOL.read_bytes()
    protocol = json.loads(raw, object_pairs_hook=v4._unique_pairs)
    if (
        _sha(v12_verify.PROTOCOL.read_bytes()) != BASELINE_PROTOCOL_SHA
        or _sha(v12_verify.JOURNAL.read_bytes()) != BASELINE_JOURNAL_SHA
    ):
        raise ValueError("baseline artifact differs")
    baseline = v12_verify.verify()
    baseline_protocol = json.loads(
        v12_verify.PROTOCOL.read_bytes(), object_pairs_hook=v4._unique_pairs
    )
    _identity(protocol, baseline, baseline_protocol)
    head = (
        subprocess.run(("git", "rev-parse", "HEAD"), cwd=ROOT, check=True, capture_output=True)
        .stdout.decode()
        .strip()
    )
    if _frozen(head, PROTOCOL.relative_to(ROOT).as_posix()) != raw:
        raise ValueError("protocol must be committed")
    for path, digest in protocol["source_sha256"].items():
        if digest != _sha(_frozen(protocol["frozen_code_commit"], path)) or (
            path not in POSTRUN_REVIEW_FILES and digest != _sha((ROOT / path).read_bytes())
        ):
            raise ValueError("frozen source differs")
    cases = v5._load_cases(v5.DATA.read_bytes())
    policy = v5._policy(protocol)
    requests = {}
    for name in ORDER:
        case_id, candidate_id = name.split("-", 1)
        old, new = _request(cases[case_id], candidate_id, policy)
        if _sha(old) != baseline_protocol["request_sha256"][name]:
            raise ValueError("baseline request differs")
        requests[name] = new
    if protocol["request_sha256"] != {name: _sha(body) for name, body in requests.items()}:
        raise ValueError("independent request differs")
    journal_raw = JOURNAL.read_bytes()
    rows = [
        json.loads(line, object_pairs_hook=v4._unique_pairs)
        for line in journal_raw.decode().splitlines()
    ]
    counts = _rows(rows, _sha(raw), protocol)
    if PRIVATE_DIR.is_symlink() or stat.S_IMODE(PRIVATE_DIR.stat().st_mode) != 0o700:
        raise ValueError("private directory differs")
    expected_files = {
        f"{row['call']}.json.txt" for row in rows[1:] if row["raw_sha256"] is not None
    }
    if {path.name for path in PRIVATE_DIR.iterdir()} != expected_files:
        raise ValueError("private file set differs")
    reviewed = json.loads(v12_verify.LABELS.read_bytes(), object_pairs_hook=v4._unique_pairs)
    labels = {row["call"]: row for row in reviewed["cases"]}
    if set(labels) != set(ORDER):
        raise ValueError("reviewed labels differ")
    baseline_rows = {row["call"]: row for row in baseline["per_call"]}
    baseline_raw = {
        row["call"]: row["raw_sha256"]
        for row in _baseline_journal_rows()
        if row.get("event") == "result"
    }
    results = []
    for row in rows[1:]:
        name = row["call"]
        if row["raw_sha256"] is None:
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
                raise ValueError("private response permissions differ")
            response = path.read_bytes()
            if _sha(response) != row["raw_sha256"] or len(response) != row["raw_bytes"]:
                raise ValueError("private response differs")
            if row["finish_reason"] == "stop":
                score = v12_verify._score(
                    response,
                    len(split_clauses(cases[name.split("-", 1)[0]]["user_message"])),
                    labels[name],
                )
                if row["error_code"] != score["contract_error"]:
                    raise ValueError("journal contract error differs")
            else:
                score = {
                    "contract_valid": False,
                    "contract_error": "finish_length",
                    "relation_status": None,
                    "status_exact": None,
                    "evidence_clause_exact": None,
                }
        results.append(
            {
                "call": name,
                "error_code": row["error_code"],
                "raw_matches_v12": row["raw_sha256"] is not None
                and row["raw_sha256"] == baseline_raw[name],
                "baseline_status": baseline_rows[name]["relation_status"],
                **score,
            }
        )
    return {
        "kind": "as_safety_label_order_v16_verification_v1",
        "protocol_sha256": _sha(raw),
        "journal_sha256": _sha(journal_raw),
        "calls_completed": len(results),
        "contract_pass_count": sum(item["contract_valid"] for item in results),
        "status_exact_count": sum(item["status_exact"] is True for item in results),
        "evidence_clause_exact_count": sum(
            item["evidence_clause_exact"] is True for item in results
        ),
        "supported_count": sum(item["relation_status"] == "supported" for item in results),
        "input_tokens": counts,
        "per_call": results,
        "official_accuracy_evaluated": False,
    }


def _baseline_journal_rows() -> list[dict]:
    return [
        json.loads(line, object_pairs_hook=v4._unique_pairs)
        for line in v12_verify.JOURNAL.read_text().splitlines()
    ]


def main() -> None:
    print(json.dumps(verify(), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
