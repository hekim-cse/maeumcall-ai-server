"""Development-only focused Q5 safety probe on already exposed PF cases.

This does not change the service workflow or produce a heldout accuracy claim.
Only bounded decisions and timing are saved, never prompts or completions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path

from evals.structured_nlu.ai_heldout import AIHeldoutDataset, AIHeldoutRequestPolicy
from scripts.run_ai_heldout_pair import _loopback_endpoint, _post_completion

SYSTEM_PROMPT = (
    "너는 A/S 접수의 안전 위험만 판정한다. 사용자가 현재 A/S 대상 제품에서 "
    "실제로 발생했다고 말한 연기, 심한 발열, 타는 냄새, 배터리 변형, 불꽃, "
    "전선 피복 손상은 true다. 다른 사람·다른 제품의 경험, 후기, 가정, "
    "발생 여부 질문, 명시적 부정은 false다. JSON 객체 하나만 반환한다: "
    '{"current_safety_issue": true 또는 false}'
)


def _sha256(path: Path) -> str:
    """Hash the exact diagnostic input bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args: argparse.Namespace) -> dict:
    """Call the local model once per exposed case and save bounded telemetry."""
    endpoint = _loopback_endpoint(args.endpoint)
    dataset = AIHeldoutDataset.model_validate_json(args.dataset.read_bytes())
    if [case.id for case in dataset.cases] != [
        f"nlu-safety-postfreeze-pf{i:02}" for i in range(1, 17)
    ]:
        raise ValueError("focused probe requires exposed PF01–PF16")
    if args.output.exists():
        raise ValueError("development result already exists")
    policy = AIHeldoutRequestPolicy.model_validate_json(args.policy.read_bytes())
    policy = policy.model_copy(update={"max_tokens": 48})
    rows = []
    for index, case in enumerate(dataset.cases):
        started = time.perf_counter()
        error_type = None
        decision = None
        try:
            raw = _post_completion(
                endpoint,
                "/models/kanana.gguf",
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": case.user_message},
                ],
                policy,
            )
            parsed = json.loads(raw)
            if not isinstance(parsed, dict) or set(parsed) != {"current_safety_issue"}:
                raise ValueError("focused response keys differ")
            if not isinstance(parsed["current_safety_issue"], bool):
                raise ValueError("focused response is not boolean")
            decision = parsed["current_safety_issue"]
        except (OSError, TimeoutError, ValueError, TypeError, KeyError) as error:
            error_type = type(error).__name__
        rows.append(
            {
                "case_id": case.id,
                "expected_safety": index < 8,
                "current_safety_issue": decision,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "error_type": error_type,
            }
        )
        print(case.id, decision, error_type, flush=True)
    latencies = [row["latency_ms"] for row in rows]
    result = {
        "kind": "safety_focus_exposed_development_probe_v1",
        "claim_scope": "already_exposed_ai_authored_pf_development_only",
        "dataset_sha256": _sha256(args.dataset),
        "request_policy_sha256": _sha256(args.policy),
        "model_sha256": _sha256(args.model_path),
        "probe_sha256": _sha256(Path(__file__)),
        "max_tokens": policy.max_tokens,
        "summary": {
            "positive_correct": sum(row["current_safety_issue"] is True for row in rows[:8]),
            "positive_denominator": 8,
            "negative_correct": sum(row["current_safety_issue"] is False for row in rows[8:]),
            "negative_denominator": 8,
            "invalid_responses": sum(row["error_type"] is not None for row in rows),
            "median_latency_ms": round(statistics.median(latencies), 3),
        },
        "cases": rows,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def main() -> None:
    """Parse one local development probe invocation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    result = run(parser.parse_args())
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
