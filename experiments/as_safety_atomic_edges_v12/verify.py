"""Independently replay frozen pair requests and restricted raw responses."""

from __future__ import annotations

import hashlib
import json
import stat
import subprocess
from pathlib import Path

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v4 import run as v4
from experiments.as_safety_atomic_edges_v5 import run as v5
from experiments.as_safety_atomic_edges_v9 import verify as v9_verify
from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.quotes import anchor_span, split_clauses

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
PROTOCOL = DATA / "as-safety-eb-pair-v12-development-protocol.json"
JOURNAL = DATA / "as-safety-eb-pair-v12-development-journal.v1.jsonl"
LABELS = DATA / "as-safety-eb-pair-v12-reviewed.json"
PRIVATE_DIR = Path("/private/tmp/as-safety-eb-pair-v12-raw")
ORDER = ("PC01-P014", "PC01-P016", "NC01-P020", "NC01-P002")
EXPECTED_SOURCES = v5.SOURCE_PATHS | {
    "docs/portfolio/nlu_safety_eb_pair_relation_v12_design.md",
    "docs/portfolio/nlu_safety_eb_pair_relation_v12_review.md",
    "evals/structured_nlu/data/ai_heldout/as-safety-eb-pair-v12-reviewed.json",
    "experiments/as_safety_v2/source_lattice.py",
    "experiments/as_safety_atomic_edges_v7/run.py",
    "experiments/as_safety_atomic_edges_v8/boundary_audit.py",
    "experiments/as_safety_atomic_edges_v9/verify.py",
    "experiments/as_safety_atomic_edges_v10/candidate_contract.py",
    "experiments/as_safety_atomic_edges_v10/model_attestation.py",
    "experiments/as_safety_atomic_edges_v10/probe.py",
    "experiments/as_safety_atomic_edges_v10/run.py",
    "experiments/as_safety_atomic_edges_v12/pair_contract.py",
    "experiments/as_safety_atomic_edges_v12/run.py",
    "experiments/as_safety_atomic_edges_v12/verify.py",
    "tests/test_as_safety_pair_relation_v12.py",
    "tests/test_as_safety_pair_run_v12.py",
}
STATUSES = frozenset({"supported", "unsupported", "insufficient"})


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _frozen(commit: str, relative: str) -> bytes:
    if (
        type(commit) is not str
        or len(commit) != 40
        or any(c not in "0123456789abcdef" for c in commit)
        or relative.startswith("/")
        or ".." in Path(relative).parts
    ):
        raise ValueError("frozen source reference invalid")
    return subprocess.run(
        ("git", "show", f"{commit}:{relative}"), cwd=ROOT, check=True, capture_output=True
    ).stdout


def _request(case: dict, candidate_id: str, policy) -> bytes:
    rows, lattice = v9_verify._candidate_rows(case, "N")
    if lattice.truncated:
        raise ValueError("candidate list truncated")
    selected = [row for row in rows if row.startswith(f"{candidate_id} | ")]
    if len(selected) != 1:
        raise ValueError("candidate ID not uniquely offered")
    source = case["user_message"]
    clauses = split_clauses(source)
    event = anchor_span(case["event_span"], clauses, field="event_span")
    if event is None:
        raise ValueError("event span missing")
    numbered = "\n".join(f"{index}. {clause}" for index, clause in enumerate(clauses, 1))
    messages = [
        {
            "role": "system",
            "content": (
                "제시한 후보 구절이 위험 사건 E의 물리적 출처인지 원문에 근거해 판단하세요. "
                "후보가 원문에 있다는 사실만으로 연결을 확정하지 마세요."
            ),
        },
        {
            "role": "user",
            "content": (
                f"원문 전체: {source}\n번호 문장:\n{numbered}\n"
                f"검수된 위험 사건 E: {event['clause_index']}. {event['quote']}\n"
                f"판단할 후보 B: {selected[0]}\n"
                "relation_status는 supported(원문이 이 후보를 사건의 물리적 출처로 뒷받침함), "
                "unsupported(이 후보는 현상 자체이거나 원문과 모순되어 출처가 될 수 없음), "
                "insufficient(가능성은 있으나 원문만으로 출처를 확정할 수 없음) 중 하나입니다. "
                "supported 또는 unsupported라면 근거가 있는 문장 번호를 "
                "evidence_clause_index에 적으세요. insufficient라면 불확실성을 명시한 문장 번호가 "
                "있을 때만 적고, 없으면 null로 두세요. 문장 번호는 근거 위치를 가리킬 뿐 "
                "관계의 진실성을 자동 증명하지 않습니다. 다른 후보를 제안하거나 접수 제품 소속·"
                "안전 경로를 판단하지 마세요. 두 키의 JSON 객체만 반환하세요."
            ),
        },
    ]
    schema = {
        "type": "object",
        "properties": {
            "relation_status": {"enum": sorted(STATUSES)},
            "evidence_clause_index": {
                "anyOf": [{"enum": list(range(1, len(clauses) + 1))}, {"type": "null"}]
            },
        },
        "required": ["evidence_clause_index", "relation_status"],
        "additionalProperties": False,
    }
    return v4.request_bytes(messages, schema, policy, "variant")


def _score(raw: bytes, clause_count: int, gold: dict) -> dict:
    try:
        parsed = parse_model_json(raw.decode("utf-8"))
        if type(parsed) is not dict or set(parsed) != {"relation_status", "evidence_clause_index"}:
            raise ValidationError("fields_invalid", "candidate_relation")
        status = parsed["relation_status"]
        index = parsed["evidence_clause_index"]
        if type(status) is not str or status not in STATUSES:
            raise ValidationError("relation_status_invalid", "relation_status")
        if index is not None and (type(index) is not int or not 1 <= index <= clause_count):
            raise ValidationError("evidence_clause_invalid", "evidence_clause_index")
        if status != "insufficient" and index is None:
            raise ValidationError("evidence_clause_missing", "evidence_clause_index")
    except (UnicodeDecodeError, ValidationError) as error:
        return {
            "contract_valid": False,
            "contract_error": getattr(error, "code", "response_utf8_invalid"),
            "relation_status": None,
            "status_exact": None,
            "evidence_clause_exact": None,
        }
    return {
        "contract_valid": True,
        "contract_error": None,
        "relation_status": status,
        "status_exact": status == gold["relation_status"],
        "evidence_clause_exact": index == gold["evidence_clause_index"],
    }


def verify() -> dict:
    protocol_raw = PROTOCOL.read_bytes()
    protocol = json.loads(protocol_raw, object_pairs_hook=_unique)
    expected_fields = {
        "kind",
        "scope",
        "order",
        "frozen_code_commit",
        "source_sha256",
        "cases_sha256",
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
        or set(protocol) != expected_fields
        or protocol["kind"] != "as_safety_eb_pair_v12_development_v1"
        or protocol["order"] != list(ORDER)
        or set(protocol["source_sha256"]) != EXPECTED_SOURCES
        or protocol["model_sha256"] != v1.MODEL_SHA
        or protocol["image_digest"] != v1.IMAGE
        or protocol["journal"] != JOURNAL.relative_to(ROOT).as_posix()
        or protocol["private_output"] != "outside_repository_mode_0700_files_0600"
    ):
        raise ValueError("protocol identity differs")
    current = (
        subprocess.run(("git", "rev-parse", "HEAD"), cwd=ROOT, check=True, capture_output=True)
        .stdout.decode()
        .strip()
    )
    if _frozen(current, PROTOCOL.relative_to(ROOT).as_posix()) != protocol_raw:
        raise ValueError("protocol not committed")
    for path, digest in protocol["source_sha256"].items():
        if _sha(_frozen(protocol["frozen_code_commit"], path)) != digest:
            raise ValueError("frozen source differs")
        if _sha((ROOT / path).read_bytes()) != digest:
            raise ValueError("current source differs from frozen code")
    if _sha(v5.DATA.read_bytes()) != protocol["cases_sha256"]:
        raise ValueError("case source differs")
    reviewed = json.loads(LABELS.read_bytes(), object_pairs_hook=_unique)
    if reviewed["kind"] != "as_safety_eb_pair_v12_user_reviewed_development_labels" or [
        item["call"] for item in reviewed["cases"]
    ] != list(ORDER):
        raise ValueError("reviewed labels differ")
    labels = {item["call"]: item for item in reviewed["cases"]}
    cases = v5._load_cases(v5.DATA.read_bytes())
    policy = v5._policy(protocol)
    requests = {
        name: _request(cases[name.split("-", 1)[0]], name.split("-", 1)[1], policy)
        for name in ORDER
    }
    if protocol["request_sha256"] != {name: _sha(body) for name, body in requests.items()}:
        raise ValueError("request differs from frozen protocol")
    journal_raw = JOURNAL.read_bytes()
    rows = [
        json.loads(line, object_pairs_hook=_unique) for line in journal_raw.decode().splitlines()
    ]
    if not rows or rows[0] != {"event": "header", "protocol_sha256": _sha(protocol_raw)}:
        raise ValueError("journal header differs")
    if not 1 <= len(rows) - 1 <= len(ORDER) or [row["call"] for row in rows[1:]] != list(
        ORDER[: len(rows) - 1]
    ):
        raise ValueError("journal order differs")
    if PRIVATE_DIR.is_symlink() or stat.S_IMODE(PRIVATE_DIR.stat().st_mode) != 0o700:
        raise ValueError("private directory mode differs")
    expected_files = {
        f"{row['call']}.json.txt" for row in rows[1:] if row["raw_sha256"] is not None
    }
    if {path.name for path in PRIVATE_DIR.iterdir()} != expected_files:
        raise ValueError("private raw file set differs")
    results = []
    for row in rows[1:]:
        name = row["call"]
        case_id = name.split("-", 1)[0]
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
            raw = path.read_bytes()
            if _sha(raw) != row["raw_sha256"] or len(raw) != row["raw_bytes"]:
                raise ValueError("private raw digest differs")
            score = (
                _score(raw, len(split_clauses(cases[case_id]["user_message"])), labels[name])
                if row["finish_reason"] == "stop"
                else {
                    "contract_valid": False,
                    "contract_error": row["error_code"] or "finish_length",
                    "relation_status": None,
                    "status_exact": None,
                    "evidence_clause_exact": None,
                }
            )
        results.append({"call": name, "error_code": row["error_code"], **score})
    gate = len(results) == len(ORDER) and all(
        item["error_code"] is None
        and item["contract_valid"]
        and item["status_exact"] is True
        and item["evidence_clause_exact"] is True
        for item in results
    )
    return {
        "kind": "as_safety_eb_pair_v12_development_verification_v1",
        "protocol_sha256": _sha(protocol_raw),
        "journal_sha256": _sha(journal_raw),
        "calls_completed": len(results),
        "contract_pass_count": sum(item["contract_valid"] for item in results),
        "status_exact_count": sum(item["status_exact"] is True for item in results),
        "evidence_clause_exact_count": sum(
            item["evidence_clause_exact"] is True for item in results
        ),
        "per_call": results,
        "pair_gate_pass": gate,
        "official_accuracy_evaluated": False,
    }


def main() -> None:
    print(json.dumps(verify(), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
