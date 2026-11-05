"""Pair baseline and fixed semantic prompts on user-reviewed AI development drafts."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.semantic_boundary_policy import POLICY_BY_SCENARIO
from evals.structured_nlu.semantic_boundary_review import (
    DEFAULT_DRAFT,
    EXPOSURE_RECORD,
    FIELD_DRAFT,
    REVIEW_LEDGER,
    load_field_draft,
    load_review_draft,
)
from scripts.probe_gguf_field_boundary import inspect_runtime
from scripts.probe_gguf_structured_nlu import run_case

ROOT = Path(__file__).resolve().parents[1]
MODEL = "kanana-1.5-2.1b-instruct-q5"
SOURCE_PATHS = (
    "scripts/probe_gguf_semantic_boundary_pair.py",
    "scripts/probe_gguf_structured_nlu.py",
    "evals/structured_nlu/semantic_boundary_review.py",
    "evals/structured_nlu/semantic_boundary_policy.py",
)


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _case_for_runner(sentence: dict, field_draft: dict) -> dict:
    contract = EVALUATION_CONTRACTS[sentence["scenario_key"]]
    fields = field_draft["fields"]
    return {
        "id": sentence["id"],
        "scenario_key": sentence["scenario_key"],
        "conversation_state": sentence["conversation_state"],
        "current_fields": dict.fromkeys(contract.field_names)
        if contract.uses_current_fields
        else {},
        "offered_alternative_times": [],
        "user_message": sentence["user_message"],
        "labels": {
            "intent": contract.workflow_spec.intent if contract.workflow_spec else "reservation",
            "user_action": sentence["action_draft"],
            "change_field": None,
            "fields": {
                name: None if value is None else {"accepted_values": [value]}
                for name, value in fields.items()
            },
        },
    }


def _safe_observation(sentence: dict, mode: str, repetition: int, result: dict) -> dict:
    mismatches = result.get("draft_label_mismatch_fields", [])
    passed = result["contract_valid"]
    return {
        "case_id": sentence["id"],
        "mode": mode,
        "repetition": repetition,
        "contract_valid": passed,
        "action_matches_draft": passed and "user_action" not in mismatches,
        "focus_field_matches_draft": passed and sentence["field"] not in mismatches,
        "all_fields_and_action_match_draft": passed and not mismatches,
        "draft_mismatch_names": mismatches,
        "elapsed_seconds": result["elapsed_seconds"],
        "attempts": result["attempts"],
        **({"failure": result["failure"]} if "failure" in result else {}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container-name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=2)
    args = parser.parse_args()
    if args.output.exists() or args.repetitions < 1:
        parser.error("output must not exist and repetitions must be positive")
    sentences = load_review_draft(for_model_run=True)
    field_drafts = load_field_draft(for_model_run=True)
    cases = [
        (sentence, _case_for_runner(sentence, field_draft))
        for sentence, field_draft in zip(sentences, field_drafts, strict=True)
    ]
    runtime = inspect_runtime(args.container_name)
    source_hashes = {name: _sha256(ROOT / name) for name in SOURCE_PATHS}
    input_hashes = {
        "sentences": _sha256(DEFAULT_DRAFT),
        "fields": _sha256(FIELD_DRAFT),
        "review_ledger": _sha256(REVIEW_LEDGER),
    }
    exposure = {
        "kind": "semantic_boundary_model_exposure_v1",
        "started_at_utc": datetime.now(UTC).isoformat(),
        "case_ids": [sentence["id"] for sentence in sentences],
        "input_sha256": input_hashes,
        "model_sha256": runtime["model_sha256"],
    }
    with EXPOSURE_RECORD.open("x", encoding="utf-8") as stream:
        json.dump(exposure, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    observations = []
    try:
        for repetition in range(1, args.repetitions + 1):
            ordered = cases if repetition % 2 else list(reversed(cases))
            modes = ("baseline", "candidate") if repetition % 2 else ("candidate", "baseline")
            for sentence, case in ordered:
                for mode in modes:
                    result = run_case(
                        case,
                        endpoint=runtime["endpoint"],
                        model=MODEL,
                        timeout=180,
                        capture_shape=True,
                        extra_instruction=(
                            POLICY_BY_SCENARIO[sentence["scenario_key"]]
                            if mode == "candidate"
                            else None
                        ),
                    )
                    observations.append(_safe_observation(sentence, mode, repetition, result))
                    print(
                        f"{len(observations)} {sentence['id']} {mode} "
                        f"contract={result['contract_valid']}",
                        flush=True,
                    )
    finally:
        report = {
            "kind": "exploratory_q5_semantic_boundary_pair_v1",
            "not_official_quality_score": True,
            "complete": len(observations) == len(cases) * args.repetitions * 2,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "case_ids": [sentence["id"] for sentence in sentences],
            "repetitions": args.repetitions,
            "source_sha256": source_hashes,
            "input_sha256": input_hashes,
            "exposure_record_sha256": _sha256(EXPOSURE_RECORD),
            "model_sha256": runtime["model_sha256"],
            "server_image_digest": runtime["server_image_digest"],
            "runtime": {key: value for key, value in runtime.items() if key != "endpoint"},
            "request_settings": {
                "max_tokens": 180,
                "temperature": 0,
                "repeat_penalty": 1.05,
                "stop": ["<|eot_id|>"],
            },
            "observations": observations,
        }
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
