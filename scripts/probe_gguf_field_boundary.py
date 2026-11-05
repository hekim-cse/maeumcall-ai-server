"""Temporary paired development probe; never records prompt or completion text."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.action_field_dev_cases import load_cases as load_development_cases
from scripts.fresh_scope_ai_cases import load_cases as load_fresh_cases
from scripts.probe_gguf_structured_nlu import run_case

MODEL_SHA256 = "644b04cde835d486df33c6d4d7552ba367fcb28802fe39b6b4bb9c60b9ab6f3d"
IMAGE_DIGEST = "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
CASE_IDS = ("F15", "F17", "F23", "F29", "D05")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("baseline", "candidate"), required=True)
    parser.add_argument("--constrain-workflow", action="store_true")
    parser.add_argument("--repetition", type=int, choices=(1, 2), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = {case["id"]: case for case in [*load_fresh_cases(), *load_development_cases()]}
    selected = tuple(
        case_id for case_id in CASE_IDS if not args.constrain_workflow or case_id != "F29"
    )
    order = selected if args.repetition == 1 else tuple(reversed(selected))
    observations = []
    for case_id in order:
        result = run_case(
            cases[case_id],
            endpoint="http://127.0.0.1:18080/v1/chat/completions",
            model="kanana-1.5-2.1b-instruct-q5",
            timeout=180,
            capture_shape=True,
            constrain_workflow=args.constrain_workflow,
            schema_format="json_object",
        )
        observations.append(result)
        print(
            f"{args.mode} r{args.repetition} {case_id} contract={result['contract_valid']}",
            flush=True,
        )
    files = (
        "services/flow/service_workflow/structured.py",
        "services/flow/reservation/study_room/llm_structured.py",
        "services/flow/delivery/contracts.py",
    )
    source_sha256 = {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in files}
    report = {
        "kind": "exploratory_nlu_boundary_pair_v1",
        "not_official_quality_score": True,
        "mode": args.mode,
        "constrain_workflow": args.constrain_workflow,
        "schema_format": "json_object" if args.constrain_workflow else None,
        "repetition": args.repetition,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "case_ids": list(order),
        "source_sha256": source_sha256,
        "model_sha256": MODEL_SHA256,
        "server_image_digest": IMAGE_DIGEST,
        "runtime": "local-docker-arm-cpu",
        "container_cpu_limit": 4,
        "container_memory_gib": 6,
        "server_threads": 4,
        "server_parallel": 1,
        "context_size": 4096,
        "observations": observations,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
