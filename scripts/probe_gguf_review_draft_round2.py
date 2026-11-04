"""Explore AI-assisted draft cases against a local OpenAI-compatible GGUF server.

This probe does not run the official benchmark or claim model accuracy. It saves
case IDs, contract outcomes, and mismatched draft-label names without model text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.probe_gguf_structured_nlu import run_case
from scripts.validate_nlu_review_draft import LABELS, SENTENCES, load_draft_cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:18080/v1/chat/completions")
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--server-image-digest", required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--container-cpu-limit", required=True, type=int)
    parser.add_argument("--server-threads", required=True, type=int)
    parser.add_argument("--context-size", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--capture-shape", action="store_true")
    parser.add_argument("--constrain-workflow", action="store_true")
    parser.add_argument("--split-workflow", action="store_true")
    parser.add_argument(
        "--schema-format", choices=("json_schema", "json_object"), default="json_schema"
    )
    parser.add_argument("--sentence-source", type=Path, default=SENTENCES)
    args = parser.parse_args()
    if (
        min(args.timeout, args.container_cpu_limit, args.server_threads, args.context_size) < 1
        or args.output.exists()
    ):
        parser.error("numeric settings must be positive and output must not already exist")
    if args.split_workflow and (not args.constrain_workflow or args.schema_format != "json_object"):
        parser.error("split workflow requires --constrain-workflow --schema-format json_object")

    all_cases = load_draft_cases(sentences_path=args.sentence_source)
    by_id = {case["id"]: case for case in all_cases}
    unknown_ids = sorted(set(args.case_id) - set(by_id))
    if unknown_ids:
        parser.error(f"unknown case IDs: {unknown_ids}")
    if len(args.case_id) != len(set(args.case_id)):
        parser.error("case IDs must not be repeated")
    cases = [by_id[case_id] for case_id in args.case_id] if args.case_id else all_cases
    observations = []
    try:
        for index, case in enumerate(cases, start=1):
            observation = run_case(
                case,
                endpoint=args.endpoint,
                model=args.model,
                timeout=args.timeout,
                capture_shape=args.capture_shape,
                constrain_workflow=args.constrain_workflow,
                schema_format=args.schema_format,
                split_workflow=args.split_workflow,
            )
            observations.append(observation)
            print(
                f"{index}/{len(cases)} case={case['id']} "
                f"contract_valid={observation['contract_valid']}",
                flush=True,
            )
    finally:
        report = {
            "kind": "exploratory_gguf_review_draft_round2_v1",
            "candidate_status": "ai_assisted_unreviewed",
            "not_official_quality_score": True,
            "output_shape_capture": args.capture_shape,
            "workflow_schema_constrained": args.constrain_workflow,
            "action_field_split": args.split_workflow,
            "schema_format": args.schema_format if args.constrain_workflow else None,
            "complete": len(observations) == len(cases),
            "created_at_utc": datetime.now(UTC).isoformat(),
            "sentence_draft_sha256": hashlib.sha256(args.sentence_source.read_bytes()).hexdigest(),
            "label_draft_sha256": hashlib.sha256(LABELS.read_bytes()).hexdigest(),
            "model": args.model,
            "model_sha256": args.model_sha256,
            "server_image_digest": args.server_image_digest,
            "runtime": args.runtime,
            "container_cpu_limit": args.container_cpu_limit,
            "server_threads": args.server_threads,
            "context_size": args.context_size,
            "request_settings": {
                "max_tokens": 180,
                "temperature": 0,
                "repeat_penalty": 1.05,
                "stop": ["<|eot_id|>"],
            },
            "case_count": len(cases),
            "selected_case_ids": [case["id"] for case in cases],
            "observations": observations,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
