"""Development-only safety attribution using server-owned source clause IDs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

from evals.structured_nlu.ai_heldout import AIHeldoutDataset, AIHeldoutRequestPolicy
from scripts.probe_as_safety_evidence import post_constrained_completion, route_evidence
from scripts.run_ai_heldout_pair import _loopback_endpoint

PROMPT = (
    "A/S 접수 발화에서 현재 문의하는 제품의 안전 위험을 판단한다. "
    "위험 단서가 있는 원문 문장 번호 하나를 고른다. 다른 물건, 타인의 후기, "
    "인터넷 자료에 관한 위험이면 target은 other다. 현재 제품의 실제 관찰이면 "
    "target=current, assertion=observed다. 실제 관찰인지 또는 출처가 불확실하면 "
    "assertion=uncertain이다. 부정·가정 질문이면 assertion=negated_or_hypothetical이다. "
    "위험 단서가 없으면 evidence_index=null, target=none, assertion=none이다. "
    "예시: '1. 방향제에서 탄내가 납니다. 2. 제 공기청정기는 화면이 꺼집니다.'이면 "
    '{"evidence_index":1,"target":"other","assertion":"observed"}. '
    "'1. 휴대폰이 뜨거운지 모르겠어요.'이면 "
    '{"evidence_index":1,"target":"current","assertion":"uncertain"}. '
    "반드시 JSON 객체 하나만 반환한다."
)


def split_clauses(utterance: str) -> tuple[str, ...]:
    """Assign stable IDs to original sentence spans without rewriting text."""
    return tuple(part.strip() for part in re.split(r"(?<=[.!?。])\s+", utterance) if part.strip())


def evidence_schema(count: int) -> dict:
    """Constrain the selected source ID to the server's actual clauses."""
    if count < 1:
        raise ValueError("utterance has no clause")
    return {
        "type": "object",
        "properties": {
            "evidence_index": {"enum": [None, *range(1, count + 1)]},
            "target": {"enum": ["current", "other", "unknown", "none"]},
            "assertion": {"enum": ["observed", "uncertain", "negated_or_hypothetical", "none"]},
        },
        "required": ["evidence_index", "target", "assertion"],
        "additionalProperties": False,
    }


def validate_indexed_evidence(raw: str, count: int) -> dict:
    """Reject invalid IDs and contradictory empty evidence fields."""
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or set(parsed) != {"evidence_index", "target", "assertion"}:
        raise ValueError("indexed evidence keys differ")
    index = parsed["evidence_index"]
    target = parsed["target"]
    assertion = parsed["assertion"]
    if target not in {"current", "other", "unknown", "none"}:
        raise ValueError("invalid safety target")
    if assertion not in {"observed", "uncertain", "negated_or_hypothetical", "none"}:
        raise ValueError("invalid safety assertion")
    if index is None or target == "none" or assertion == "none":
        if (index, target, assertion) != (None, "none", "none"):
            raise ValueError("empty indexed evidence fields disagree")
    elif type(index) is not int or not 1 <= index <= count:
        raise ValueError("evidence index is outside source clauses")
    return parsed


def run(args: argparse.Namespace) -> None:
    """Run already exposed CF cases once; persist only bounded decisions."""
    endpoint = _loopback_endpoint(args.endpoint)
    if endpoint != "http://127.0.0.1:18081/v1/chat/completions":
        raise ValueError("unexpected local endpoint")
    if args.output.exists():
        raise ValueError("development result already exists")
    dataset = AIHeldoutDataset.model_validate_json(args.dataset.read_bytes())
    cases = dataset.cases
    if len(cases) != 32 or [case.id[-4:] for case in cases] != [
        f"cf{number:02}" for number in range(1, 33)
    ]:
        raise ValueError("expected frozen CF01–CF32 order")
    policy = AIHeldoutRequestPolicy.model_validate_json(args.policy.read_bytes())
    policy = policy.model_copy(update={"max_tokens": 100})
    rows = []
    for case in cases:
        clauses = split_clauses(case.user_message)
        source = "\n".join(f"{index}. {clause}" for index, clause in enumerate(clauses, 1))
        started = time.perf_counter()
        decision = None
        error_type = None
        try:
            raw = post_constrained_completion(
                endpoint,
                args.model_id,
                [
                    {"role": "system", "content": PROMPT},
                    {"role": "user", "content": source},
                ],
                policy,
                schema=evidence_schema(len(clauses)),
            )
            decision = validate_indexed_evidence(raw, len(clauses))
        except (OSError, TimeoutError, ValueError, KeyError, TypeError) as error:
            error_type = type(error).__name__
        rows.append(
            {
                "case_id": case.id,
                "clause_count": len(clauses),
                "evidence_index": decision["evidence_index"] if decision else None,
                "target": decision["target"] if decision else None,
                "assertion": decision["assertion"] if decision else None,
                "route": route_evidence(decision) if decision else None,
                "error_type": error_type,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        )
    result = {
        "kind": "as_safety_clause_index_exposed_development_probe_v1",
        "claim_scope": "already_exposed_ai_authored_32_case_diagnostic_only",
        "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "rows": rows,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "valid": sum(row["route"] is not None for row in rows),
                "direct": sum(row["route"] == "safety_action_required" for row in rows),
                "confirm": sum(row["route"] == "confirming_safety_status" for row in rows),
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    """Parse explicit local model and frozen development input paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model-id", default="/models/kanana.gguf")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
