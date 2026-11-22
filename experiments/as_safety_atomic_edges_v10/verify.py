"""Replay the v10 journal against frozen inputs without importing its runner."""

from __future__ import annotations

import hashlib
import json
import stat
import subprocess
from pathlib import Path

from experiments.as_safety_atomic_edges_v4 import run as v4
from experiments.as_safety_atomic_edges_v5 import run as v5
from experiments.as_safety_atomic_edges_v9 import verify as v9_verify
from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = (
    ROOT
    / "evals/structured_nlu/data/ai_heldout/as-safety-eb-candidate-id-v10-development-protocol.json"
)
JOURNAL = (
    ROOT
    / "evals/structured_nlu/data/ai_heldout/as-safety-eb-candidate-id-v10-development-journal.v1.jsonl"
)
PRIVATE_DIR = Path("/private/tmp/as-safety-eb-candidate-id-v10-raw")
ORDER = ("PC01", "NC01")
VERIFIER_PATH = "experiments/as_safety_atomic_edges_v10/verify.py"
EXPECTED_SOURCES = v5.SOURCE_PATHS | {
    "docs/portfolio/nlu_safety_eb_candidate_id_v10_method.md",
    "experiments/as_safety_v2/source_lattice.py",
    "experiments/as_safety_atomic_edges_v7/run.py",
    "experiments/as_safety_atomic_edges_v8/boundary_audit.py",
    "experiments/as_safety_atomic_edges_v9/verify.py",
    "experiments/as_safety_atomic_edges_v10/candidate_contract.py",
    "experiments/as_safety_atomic_edges_v10/model_attestation.py",
    "experiments/as_safety_atomic_edges_v10/probe.py",
    "experiments/as_safety_atomic_edges_v10/run.py",
    "experiments/as_safety_atomic_edges_v10/verify.py",
    "tests/test_as_safety_candidate_id_probe_v10.py",
}
_BOUNDARY = "E와 연결된 주체 또는 위치 B의 짧은 원문 구절을 subject_span에 인용하세요. "
_INSTRUCTION = (
    "아래 후보는 원문에서 자동 생성했으며 정답 표시가 아닙니다. "
    "검수된 위험 사건 E의 실제 물리적 출처를 확인할 수 있으면 후보 ID 하나만 candidate_id로 선택하세요. "
    "event_subject_kind는 subject(명시 주체), location(발생 위치), "
    "implicit(앞선 문맥의 주체), unresolved(확인 불가) 중 하나입니다. "
    "출처를 확인할 수 없으면 candidate_id=null, event_subject_kind=unresolved로 반환하세요. "
    "후보가 있어도 사건과 연결할 수 없으면 공란으로 보류하세요. "
    "원문 구절을 출력하지 말고 candidate_id와 event_subject_kind 두 키의 JSON 객체만 반환하세요. "
    "B가 접수 제품 A에 속하는지와 최종 안전 경로는 판단하지 마세요.\n"
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _frozen(commit: str, relative: str) -> bytes:
    if (
        type(commit) is not str
        or len(commit) != 40
        or any(c not in "0123456789abcdef" for c in commit)
    ):
        raise ValueError("frozen commit invalid")
    if relative.startswith("/") or ".." in Path(relative).parts:
        raise ValueError("frozen path invalid")
    return subprocess.run(
        ("git", "show", f"{commit}:{relative}"), cwd=ROOT, check=True, capture_output=True
    ).stdout


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _catalog(case: dict) -> tuple[list[str], dict]:
    rows, lattice = v9_verify._candidate_rows(case, "N")
    if lattice.truncated:
        raise ValueError("source candidate list truncated")
    selected = [row.split(" | ", 1)[0] for row in rows]
    by_id = {candidate.id: candidate for candidate in lattice.candidates}
    if len(selected) != len(set(selected)) or any(item not in by_id for item in selected):
        raise ValueError("candidate IDs invalid")
    return rows, {item: by_id[item] for item in selected}


def _request(case: dict, policy) -> bytes:
    rows, selected = _catalog(case)
    event = {"event_span": case["event_span"], "occurrence": case["occurrence"]}
    original = v4.messages(case, event, "variant")
    user = original[1]["content"]
    if user.count(_BOUNDARY) != 1:
        raise ValueError("prompt context differs")
    messages = [
        original[0],
        {"role": "user", "content": user.split(_BOUNDARY, 1)[0] + _INSTRUCTION + "\n".join(rows)},
    ]
    schema = {
        "type": "object",
        "properties": {
            "candidate_id": {"anyOf": [{"enum": list(selected)}, {"type": "null"}]},
            "event_subject_kind": {"enum": ["implicit", "location", "subject", "unresolved"]},
        },
        "required": ["candidate_id", "event_subject_kind"],
        "additionalProperties": False,
    }
    return v4.request_bytes(messages, schema, policy, "variant")


def _score(raw: bytes, case: dict) -> dict:
    try:
        parsed = parse_model_json(raw.decode("utf-8"))
        if type(parsed) is not dict or set(parsed) != {"candidate_id", "event_subject_kind"}:
            raise ValidationError("fields_invalid", "candidate_selection")
        candidate_id = parsed["candidate_id"]
        kind = parsed["event_subject_kind"]
        if type(kind) is not str or kind not in {"subject", "location", "implicit", "unresolved"}:
            raise ValidationError("subject_kind_invalid", "event_subject_kind")
        _, selected = _catalog(case)
        if candidate_id is None:
            if kind != "unresolved":
                raise ValidationError("selection_consistency_invalid", "candidate_id")
            subject = None
        elif type(candidate_id) is not str or candidate_id not in selected:
            raise ValidationError("candidate_not_offered", "candidate_id")
        else:
            if kind == "unresolved":
                raise ValidationError("selection_consistency_invalid", "event_subject_kind")
            item = selected[candidate_id]
            subject = {"clause_index": item.clause_index, "quote": item.quote}
    except (UnicodeDecodeError, ValidationError) as error:
        return {
            "contract_valid": False,
            "contract_error": getattr(error, "code", "response_utf8_invalid"),
            "candidate_id": None,
            "B_exact": None,
            "kind_exact": None,
            "valid_hold": None,
        }
    gold = case["gold_subject_span"]
    return {
        "contract_valid": True,
        "contract_error": None,
        "candidate_id": candidate_id,
        "B_exact": subject == gold if gold is not None else None,
        "kind_exact": kind == case["gold_kind"] if gold is not None else None,
        "valid_hold": subject is None and kind == "unresolved" if gold is None else None,
    }


def verify() -> dict:
    protocol_raw = PROTOCOL.read_bytes()
    protocol = json.loads(protocol_raw, object_pairs_hook=_unique)
    commit = protocol["frozen_code_commit"]
    if protocol["kind"] != "as_safety_eb_candidate_id_v10_development_v1" or protocol[
        "order"
    ] != list(ORDER):
        raise ValueError("protocol identity differs")
    if set(protocol["source_sha256"]) != EXPECTED_SOURCES:
        raise ValueError("frozen source set differs")
    if (
        _frozen(
            subprocess.run(("git", "rev-parse", "HEAD"), cwd=ROOT, check=True, capture_output=True)
            .stdout.decode()
            .strip(),
            PROTOCOL.relative_to(ROOT).as_posix(),
        )
        != protocol_raw
    ):
        raise ValueError("protocol is not committed")
    for relative, digest in protocol["source_sha256"].items():
        if _sha(_frozen(commit, relative)) != digest:
            raise ValueError("frozen source differs")
        if relative != VERIFIER_PATH and _sha((ROOT / relative).read_bytes()) != digest:
            raise ValueError("current source differs from frozen execution")
    current_verifier = (ROOT / VERIFIER_PATH).read_bytes()
    current_commit = (
        subprocess.run(("git", "rev-parse", "HEAD"), cwd=ROOT, check=True, capture_output=True)
        .stdout.decode()
        .strip()
    )
    if _frozen(current_commit, VERIFIER_PATH) != current_verifier:
        raise ValueError("post-run verifier revision is not committed")
    if _sha(v5.DATA.read_bytes()) != protocol["cases_sha256"]:
        raise ValueError("case bytes differ")
    cases = v5._load_cases(v5.DATA.read_bytes())
    policy = v5._policy(protocol)
    if protocol["request_sha256"] != {name: _sha(_request(cases[name], policy)) for name in ORDER}:
        raise ValueError("request differs from frozen protocol")
    journal_raw = JOURNAL.read_bytes()
    lines = journal_raw.decode("utf-8").splitlines()
    rows = [json.loads(line, object_pairs_hook=_unique) for line in lines]
    if not rows or rows[0] != {"event": "header", "protocol_sha256": _sha(protocol_raw)}:
        raise ValueError("journal header differs")
    if not 1 <= len(rows) - 1 <= len(ORDER):
        raise ValueError("journal row count differs")
    if [row["call"] for row in rows[1:]] != list(ORDER[: len(rows) - 1]):
        raise ValueError("journal order differs")
    if PRIVATE_DIR.is_symlink() or stat.S_IMODE(PRIVATE_DIR.stat().st_mode) != 0o700:
        raise ValueError("private directory mode differs")
    expected_raw_names = {
        f"{row['call']}.json.txt" for row in rows[1:] if row["raw_sha256"] is not None
    }
    if {path.name for path in PRIVATE_DIR.iterdir()} != expected_raw_names:
        raise ValueError("private raw file set differs")
    per_call = []
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
                "candidate_id": None,
                "B_exact": None,
                "kind_exact": None,
                "valid_hold": None,
            }
        else:
            path = PRIVATE_DIR / f"{name}.json.txt"
            if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0o600:
                raise ValueError("private raw permission differs")
            raw = path.read_bytes()
            if _sha(raw) != row["raw_sha256"] or len(raw) != row["raw_bytes"]:
                raise ValueError("private raw digest differs")
            score = (
                _score(raw, cases[name])
                if row["finish_reason"] == "stop"
                else {
                    "contract_valid": False,
                    "contract_error": row["error_code"] or "finish_length",
                    "candidate_id": None,
                    "B_exact": None,
                    "kind_exact": None,
                    "valid_hold": None,
                }
            )
        per_call.append({"call": name, "error_code": row["error_code"], **score})
    by_name = {item["call"]: item for item in per_call}
    gate = (
        len(per_call) == 2
        and all(item["contract_valid"] and item["error_code"] is None for item in per_call)
        and by_name["PC01"]["B_exact"] is True
        and by_name["PC01"]["kind_exact"] is True
        and by_name["NC01"]["valid_hold"] is True
    )
    return {
        "kind": "as_safety_eb_candidate_id_v10_development_verification_v1",
        "protocol_sha256": _sha(protocol_raw),
        "journal_sha256": _sha(journal_raw),
        "frozen_verifier_sha256": protocol["source_sha256"][VERIFIER_PATH],
        "postrun_verifier_sha256": _sha(current_verifier),
        "calls_completed": len(per_call),
        "contract_pass_count": sum(item["contract_valid"] for item in per_call),
        "per_call": per_call,
        "candidate_gate_pass": gate,
        "official_accuracy_evaluated": False,
    }


def main() -> None:
    print(json.dumps(verify(), ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
