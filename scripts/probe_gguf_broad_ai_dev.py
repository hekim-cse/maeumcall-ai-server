"""Run 16-scenario AI-assisted exploratory cases; never emit model text."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from scripts.broad_ai_exploration_cases import FIELD_DRAFT, SENTENCES, load_cases
from scripts.probe_gguf_structured_nlu import run_case

ROOT = Path(__file__).resolve().parents[1]
KIND = "exploratory_broad_ai_16_scenarios_v1"
REQUEST_SETTINGS = {
    "max_tokens": 180,
    "temperature": 0,
    "repeat_penalty": 1.05,
    "stop": ["<|eot_id|>"],
}
IMPLEMENTATION_PATHS = (
    "scripts/broad_ai_exploration_cases.py",
    "scripts/probe_gguf_broad_ai_dev.py",
    "scripts/probe_gguf_structured_nlu.py",
    "evals/structured_nlu/contracts.py",
    "services/flow/service_workflow/structured.py",
    "llm/structured_output.py",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def implementation_sha256() -> str:
    digest = hashlib.sha256()
    for name in IMPLEMENTATION_PATHS:
        digest.update(name.encode() + b"\0")
        digest.update((ROOT / name).read_bytes())
    return digest.hexdigest()


def summarize(observations: list[dict]) -> dict:
    valid = [item for item in observations if item["contract_valid"]]
    attempts = [attempt for item in observations for attempt in item["attempts"]]
    return {
        "observations": len(observations),
        "unique_cases": len({item["case_id"] for item in observations}),
        "contract_passes": len(valid),
        "action_draft_matches_on_contract_pass": sum(
            item["action_draft_match"] is True for item in valid
        ),
        "field_draft_matches_on_contract_pass": sum(
            item["field_draft_match"] is True for item in valid
        ),
        "full_ai_draft_matches": sum(item["draft_label_mismatch_fields"] == [] for item in valid),
        "requests": len(attempts),
        "elapsed_seconds_sum": round(sum(item["elapsed_seconds"] for item in observations), 3),
        "prompt_tokens_sum": sum(attempt["prompt_tokens"] or 0 for attempt in attempts),
        "cached_prompt_tokens_sum": sum(
            attempt["cached_prompt_tokens"] or 0 for attempt in attempts
        ),
        "completion_tokens_sum": sum(attempt["completion_tokens"] or 0 for attempt in attempts),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:18080/v1/chat/completions")
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--model-file", required=True, type=Path)
    parser.add_argument("--server-image-digest", required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--container-cpu-limit", required=True, type=int)
    parser.add_argument("--server-threads", required=True, type=int)
    parser.add_argument("--context-size", required=True, type=int)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if (
        min(
            args.container_cpu_limit,
            args.server_threads,
            args.context_size,
            args.repetitions,
            args.timeout,
        )
        < 1
    ):
        parser.error("numeric settings must be positive")
    if args.output.exists():
        parser.error("output already exists")
    if file_sha256(args.model_file) != args.model_sha256:
        parser.error("model file SHA-256 differs from declared SHA-256")
    cases = load_cases()
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--"], cwd=ROOT, check=False).returncode:
        parser.error("probe requires committed tracked files")
    code_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    code_sha = implementation_sha256()

    observations = []
    try:
        for repetition in range(1, args.repetitions + 1):
            ordered_cases = cases if repetition % 2 else list(reversed(cases))
            for case in ordered_cases:
                result = run_case(
                    case,
                    endpoint=args.endpoint,
                    model=args.model,
                    timeout=args.timeout,
                    capture_shape=True,
                )
                observations.append({"repetition": repetition, **result})
                print(
                    f"{len(observations)}/{len(cases) * args.repetitions} "
                    f"case={case['id']} contract_valid={result['contract_valid']}",
                    flush=True,
                )
    finally:
        report = {
            "kind": KIND,
            "candidate_status": "ai_assisted_unreviewed",
            "sentence_action_review": "user_accepted_for_exploration_2026-11-04",
            "normalized_value_status": "ai_draft_unreviewed",
            "not_official_quality_score": True,
            "complete": len(observations) == len(cases) * args.repetitions,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "sentence_source_sha256": file_sha256(SENTENCES),
            "field_draft_sha256": file_sha256(FIELD_DRAFT),
            "implementation_sha256": code_sha,
            "code_git_commit": code_commit,
            "model": args.model,
            "model_sha256": args.model_sha256,
            "model_file_bytes": args.model_file.stat().st_size,
            "server_image_digest": args.server_image_digest,
            "runtime": args.runtime,
            "container_cpu_limit": args.container_cpu_limit,
            "server_threads": args.server_threads,
            "context_size": args.context_size,
            "request_settings": REQUEST_SETTINGS,
            "case_ids": [case["id"] for case in cases],
            "repetitions": args.repetitions,
            "summary": summarize(observations),
            "observations": observations,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
