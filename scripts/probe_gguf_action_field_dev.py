"""Counterbalanced local GGUF probe on reviewed AI-assisted development cases.

The observations are diagnostic. They contain neither messages nor model values,
and are not official accuracy evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from scripts.action_field_dev_cases import DEFAULT_SOURCE, load_cases
from scripts.probe_gguf_structured_nlu import run_case

KIND = "exploratory_action_field_split_dev_v1"
REQUEST_SETTINGS = {
    "max_tokens": 180,
    "temperature": 0,
    "repeat_penalty": 1.05,
    "stop": ["<|eot_id|>"],
}
ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION_PATHS = (
    "scripts/action_field_dev_cases.py",
    "scripts/gguf_action_field_split.py",
    "scripts/gguf_service_workflow_schema.py",
    "scripts/probe_gguf_action_field_dev.py",
    "scripts/probe_gguf_structured_nlu.py",
    "services/flow/service_workflow/structured.py",
    "services/flow/service_workflow/structured_contract.py",
    "llm/structured_output.py",
)


def implementation_sha256() -> str:
    digest = hashlib.sha256()
    for name in IMPLEMENTATION_PATHS:
        digest.update(name.encode() + b"\0")
        digest.update((ROOT / name).read_bytes())
    return digest.hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def condition_order(case_index: int, repetition: int) -> tuple[str, str]:
    """Swap baseline and split order across neighboring cases and repetitions."""
    return ("baseline", "split") if (case_index + repetition) % 2 == 0 else ("split", "baseline")


def summarize_pairs(pairs: list[dict]) -> dict:
    summary = {"paired_observations": len(pairs), "case_count": len({p["case_id"] for p in pairs})}
    for condition in ("baseline", "split"):
        observations = [pair[condition] for pair in pairs]
        valid = [observation for observation in observations if observation["contract_valid"]]
        attempts = [attempt for observation in observations for attempt in observation["attempts"]]
        summary[condition] = {
            "contract_passes": len(valid),
            "action_draft_matches_on_contract_pass": sum(
                observation["action_draft_match"] is True for observation in valid
            ),
            "field_draft_matches_on_contract_pass": sum(
                observation["field_draft_match"] is True for observation in valid
            ),
            "full_draft_matches": sum(
                observation["draft_label_mismatch_fields"] == [] for observation in valid
            ),
            "requests": len(attempts),
            "elapsed_seconds_sum": round(
                sum(observation["elapsed_seconds"] for observation in observations), 3
            ),
            "prompt_tokens_sum": sum(attempt["prompt_tokens"] or 0 for attempt in attempts),
            "cached_prompt_tokens_sum": sum(
                attempt["cached_prompt_tokens"] or 0 for attempt in attempts
            ),
            "completion_tokens_sum": sum(attempt["completion_tokens"] or 0 for attempt in attempts),
        }
    summary["split"]["first_stage_action_draft_matches"] = sum(
        pair["split"].get("first_stage_action_draft_match") is True for pair in pairs
    )
    summary["split"]["first_stage_action_draft_observed"] = sum(
        pair["split"].get("first_stage_action_draft_match") is not None for pair in pairs
    )
    summary["paired_contract_new_passes"] = [
        f"{pair['case_id']}.r{pair['repetition']}"
        for pair in pairs
        if not pair["baseline"]["contract_valid"] and pair["split"]["contract_valid"]
    ]
    summary["paired_contract_lost_passes"] = [
        f"{pair['case_id']}.r{pair['repetition']}"
        for pair in pairs
        if pair["baseline"]["contract_valid"] and not pair["split"]["contract_valid"]
    ]
    return summary


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
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--case-id", action="append", default=[])
    args = parser.parse_args()
    if (
        min(
            args.timeout,
            args.repetitions,
            args.container_cpu_limit,
            args.server_threads,
            args.context_size,
        )
        < 1
    ):
        parser.error("numeric settings must be positive")
    if args.output.exists():
        parser.error("output already exists")
    if file_sha256(args.model_file) != args.model_sha256:
        parser.error("model file SHA-256 differs from the declared model SHA-256")
    all_cases = load_cases(args.source)
    by_id = {case["id"]: case for case in all_cases}
    if len(args.case_id) != len(set(args.case_id)) or set(args.case_id) - set(by_id):
        parser.error("case IDs must be unique known development IDs")
    cases = [by_id[case_id] for case_id in args.case_id] if args.case_id else all_cases
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--"], cwd=ROOT, check=False).returncode:
        parser.error("probe requires committed tracked files")
    implementation_digest = implementation_sha256()
    code_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()

    pairs = []
    try:
        for repetition in range(args.repetitions):
            for case_index, case in enumerate(cases):
                order = condition_order(case_index, repetition)
                observations = {}
                for condition in order:
                    observations[condition] = run_case(
                        case,
                        endpoint=args.endpoint,
                        model=args.model,
                        timeout=args.timeout,
                        capture_shape=True,
                        constrain_workflow=True,
                        schema_format="json_object",
                        split_workflow=condition == "split",
                    )
                pair = {
                    "case_id": case["id"],
                    "repetition": repetition + 1,
                    "order": list(order),
                    **observations,
                }
                pairs.append(pair)
                print(
                    f"{len(pairs)}/{len(cases) * args.repetitions} "
                    f"case={case['id']} baseline={pair['baseline']['contract_valid']} "
                    f"split={pair['split']['contract_valid']}",
                    flush=True,
                )
    finally:
        complete = len(pairs) == len(cases) * args.repetitions
        report = {
            "kind": KIND,
            "not_official_quality_score": True,
            "candidate_status": "ai_assisted_unreviewed",
            "review_scope": "user_reviewed_sentence_and_action_field_meaning",
            "normalized_value_status": "ai_draft_unreviewed",
            "complete": complete,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "case_source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
            "implementation_sha256": implementation_digest,
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
            "schema_format": "json_object",
            "case_ids": [case["id"] for case in cases],
            "repetitions": args.repetitions,
            "summary": summarize_pairs(pairs),
            "pairs": pairs,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
