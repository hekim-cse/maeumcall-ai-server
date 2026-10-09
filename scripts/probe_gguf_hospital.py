"""Exploratory hospital-case probe for a local OpenAI-compatible GGUF server.

Records timing and contract validity without storing the prompt or completion.
The development draft case is not an official quality benchmark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from services.flow.reservation.hospital.llm_structured import (
    _build_system_prompt,
    _build_user_prompt,
    _normalize_hospital_analysis_result,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evals/structured_nlu/data/compiled/gold-dataset.v2.json"
CASE_ID = "reservation-hospital-human-information-provision-001.c1"


def run_probe(endpoint: str, model: str, case: dict, timeout: int) -> dict:
    messages = [
        {"role": "system", "content": _build_system_prompt()},
        {
            "role": "user",
            "content": _build_user_prompt(
                case["conversation_state"],
                case["user_message"],
                case["offered_alternative_times"],
            ),
        },
    ]
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(
            {
                "model": model,
                "messages": messages,
                "max_tokens": 180,
                "temperature": 0,
                "repeat_penalty": 1.05,
                "stop": ["<|eot_id|>"],
            },
            ensure_ascii=False,
        ).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    elapsed = time.perf_counter() - started
    content = result["choices"][0]["message"]["content"]
    observation = {
        "elapsed_seconds": round(elapsed, 3),
        "usage": result.get("usage"),
        "finish_reason": result["choices"][0].get("finish_reason"),
    }
    try:
        parsed = json.loads(content)
        normalized = _normalize_hospital_analysis_result(
            parsed,
            conversation_state=case["conversation_state"],
            alternative_times=case["offered_alternative_times"],
        )
        observation["contract_valid"] = True
        labels = case["labels"]
        mismatched = [
            name
            for name in ("intent", "user_action", "change_field")
            if normalized.get(name) != labels[name]
        ]
        for name, expected in labels["fields"].items():
            value = normalized[name]
            if expected is None:
                if value is not None:
                    mismatched.append(name)
            elif value not in expected["accepted_values"]:
                mismatched.append(name)
        observation["draft_label_mismatch_fields"] = sorted(mismatched)
    except (ValueError, TypeError, KeyError) as exc:
        observation["contract_valid"] = False
        observation["failure_type"] = type(exc).__name__
    return observation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:18080/v1/chat/completions")
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--server-image-digest", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    if args.repeats < 1 or args.timeout < 1:
        parser.error("repeats and timeout must be positive")
    if args.output.exists():
        parser.error(f"output exists: {args.output}")

    corpus_bytes = CORPUS.read_bytes()
    case = next(case for case in json.loads(corpus_bytes)["cases"] if case["id"] == CASE_ID)
    observations = [
        run_probe(args.endpoint, args.model, case, args.timeout) for _ in range(args.repeats)
    ]
    report = {
        "kind": "exploratory_gguf_hospital_v1",
        "not_official_quality_score": True,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "case_id": CASE_ID,
        "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
        "model": args.model,
        "model_sha256": args.model_sha256,
        "server_image_digest": args.server_image_digest,
        "stop": ["<|eot_id|>"],
        "observations": observations,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"requests={len(observations)} valid={sum(x['contract_valid'] for x in observations)}")


if __name__ == "__main__":
    main()
