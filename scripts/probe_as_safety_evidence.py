"""Development-only Q5 probe for source-anchored A/S safety attribution.

This consumes already exposed CF cases. Its output is diagnostic, never a new
heldout accuracy estimate or a production routing decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path

from evals.structured_nlu.ai_heldout import AIHeldoutDataset, AIHeldoutRequestPolicy
from scripts.run_ai_heldout_pair import _loopback_endpoint, _NoRedirect

PROMPT = (
    "A/S 접수 발화에서 현재 문의하는 제품의 안전 위험 근거만 추출한다. "
    "다른 물건, 타인의 경험, 후기, 인터넷 자료, 가정 질문, 명시적 부정은 현재 제품의 실제 위험이 아니다. "
    "불확실한 관찰이나 냄새의 출처가 불분명하면 uncertain이다. "
    "evidence는 위험과 관련해 사용자가 실제 쓴 연속 문자열을 그대로 복사한다. "
    "위험 표현이 없으면 evidence는 null, target은 none, assertion은 none이다. "
    "JSON 객체 하나만 반환한다: "
    '{"evidence": string 또는 null, "target": "current"|"other"|"unknown"|"none", '
    '"assertion": "observed"|"uncertain"|"negated_or_hypothetical"|"none"}'
)
EVIDENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "evidence": {"type": ["string", "null"]},
        "target": {"enum": ["current", "other", "unknown", "none"]},
        "assertion": {"enum": ["observed", "uncertain", "negated_or_hypothetical", "none"]},
    },
    "required": ["evidence", "target", "assertion"],
    "additionalProperties": False,
}
REVIEWED_CF_DATASET_SHA256 = "67d3c23f197d80d30784d0829cbb62b606f9a4f72bcf5fa5e9ea419f191fe706"


def load_reviewed_cf_dataset(path: Path) -> tuple[AIHeldoutDataset, str]:
    """Pin the previously reviewed, already exposed CF corpus before any model call."""
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != REVIEWED_CF_DATASET_SHA256:
        raise ValueError("reviewed CF dataset SHA-256 differs")
    return AIHeldoutDataset.model_validate_json(data), digest


def post_constrained_completion(
    endpoint: str,
    model_id: str,
    messages: list[dict[str, str]],
    policy: AIHeldoutRequestPolicy,
    *,
    schema: dict | None = None,
) -> str:
    """Use llama.cpp's documented JSON Schema constrained chat output."""
    payload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": policy.max_tokens,
        "temperature": policy.temperature,
        "repeat_penalty": policy.repeat_penalty,
        "stop": list(policy.stop),
        "response_format": {"type": "json_object", "schema": schema or EVIDENCE_SCHEMA},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    with opener.open(request, timeout=policy.timeout_seconds) as response:
        body = json.load(response)
    try:
        raw = body["choices"][0]["message"]["content"]
    except IndexError as error:
        raise ValueError("model completion choices are empty") from error
    if not isinstance(raw, str):
        raise ValueError("model completion must be text")
    return raw


def validate_evidence(raw: str, utterance: str) -> dict[str, str | None]:
    """Require an exact source span and a coherent, bounded evidence schema."""
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or set(parsed) != {"evidence", "target", "assertion"}:
        raise ValueError("safety evidence keys differ")
    evidence = parsed["evidence"]
    target = parsed["target"]
    assertion = parsed["assertion"]
    if target not in {"current", "other", "unknown", "none"}:
        raise ValueError("invalid safety target")
    if assertion not in {"observed", "uncertain", "negated_or_hypothetical", "none"}:
        raise ValueError("invalid safety assertion")
    if assertion == "none" or target == "none":
        if (evidence, target, assertion) != (None, "none", "none"):
            raise ValueError("empty evidence fields disagree")
    elif not isinstance(evidence, str) or not evidence.strip() or evidence not in utterance:
        raise ValueError("evidence must be an exact nonempty source span")
    return parsed


def route_evidence(evidence: dict[str, str | None]) -> str:
    """Keep clear current hazards, uncertainty, and unrelated mentions distinct."""
    target = evidence["target"]
    assertion = evidence["assertion"]
    if target == "current" and assertion == "observed":
        return "safety_action_required"
    if target in {"current", "unknown"} and assertion in {"observed", "uncertain"}:
        return "confirming_safety_status"
    return "collecting_service_request"


def run(args: argparse.Namespace) -> None:
    """Probe one frozen, already exposed development corpus without raw text logs."""
    endpoint = _loopback_endpoint(args.endpoint)
    if endpoint != "http://127.0.0.1:18081/v1/chat/completions":
        raise ValueError("unexpected local endpoint")
    if args.output.exists():
        raise ValueError("development result already exists")
    dataset, dataset_digest = load_reviewed_cf_dataset(args.dataset)
    cases = dataset.cases
    if len(cases) != 32 or [case.id[-4:] for case in cases] != [
        f"cf{number:02}" for number in range(1, 33)
    ]:
        raise ValueError("expected frozen CF01–CF32 order")
    policy = AIHeldoutRequestPolicy.model_validate_json(args.policy.read_bytes())
    policy = policy.model_copy(update={"max_tokens": 120})
    rows = []
    for case in cases:
        started = time.perf_counter()
        decision = None
        error_type = None
        try:
            raw = post_constrained_completion(
                endpoint,
                args.model_id,
                [
                    {"role": "system", "content": PROMPT},
                    {"role": "user", "content": case.user_message},
                ],
                policy,
            )
            decision = validate_evidence(raw, case.user_message)
        except (OSError, TimeoutError, ValueError, KeyError, TypeError) as error:
            error_type = type(error).__name__
        rows.append(
            {
                "case_id": case.id,
                "target": decision["target"] if decision else None,
                "assertion": decision["assertion"] if decision else None,
                "route": route_evidence(decision) if decision else None,
                "error_type": error_type,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        )
    result = {
        "kind": "as_safety_evidence_exposed_development_probe_v2",
        "claim_scope": "already_exposed_ai_authored_32_case_diagnostic_only",
        "dataset_sha256": dataset_digest,
        "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "response_schema_sha256": hashlib.sha256(
            json.dumps(EVIDENCE_SCHEMA, sort_keys=True).encode()
        ).hexdigest(),
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
    """Accept only an explicit local endpoint and reviewed development inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model-id", default="/models/kanana.gguf")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
