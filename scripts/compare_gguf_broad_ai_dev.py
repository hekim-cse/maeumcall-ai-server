"""Verify and compare two exploratory 16-scenario GGUF probe reports."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.broad_ai_exploration_cases import FIELD_DRAFT, SENTENCES, load_cases
from scripts.probe_gguf_broad_ai_dev import KIND, file_sha256, summarize

MATCHED_SETTINGS = (
    "kind",
    "candidate_status",
    "sentence_action_review",
    "normalized_value_status",
    "not_official_quality_score",
    "sentence_source_sha256",
    "field_draft_sha256",
    "implementation_sha256",
    "code_git_commit",
    "server_image_digest",
    "runtime",
    "container_cpu_limit",
    "server_threads",
    "context_size",
    "request_settings",
    "case_ids",
    "repetitions",
)


def compare(first: dict, second: dict) -> dict:
    if first.get("kind") != KIND or second.get("kind") != KIND:
        raise ValueError("reports must be broad AI exploratory probe reports")
    if first.get("complete") is not True or second.get("complete") is not True:
        raise ValueError("both probe reports must be complete")
    if (
        first.get("candidate_status") != "ai_assisted_unreviewed"
        or first.get("normalized_value_status") != "ai_draft_unreviewed"
        or first.get("not_official_quality_score") is not True
    ):
        raise ValueError("reports must retain exploratory provenance")
    for setting in MATCHED_SETTINGS:
        if first.get(setting) != second.get(setting):
            raise ValueError(f"probe setting differs: {setting}")
    if first["model_sha256"] == second["model_sha256"] or first["model"] == second["model"]:
        raise ValueError("comparison requires different model files")
    if first["sentence_source_sha256"] != file_sha256(SENTENCES):
        raise ValueError("sentence source differs from the recorded fingerprint")
    if first["field_draft_sha256"] != file_sha256(FIELD_DRAFT):
        raise ValueError("field draft differs from the recorded fingerprint")
    if first["summary"] != summarize(first["observations"]):
        raise ValueError("first report summary differs from observations")
    if second["summary"] != summarize(second["observations"]):
        raise ValueError("second report summary differs from observations")
    cases = load_cases()
    expected_ids = [case["id"] for case in cases]
    if first["case_ids"] != expected_ids:
        raise ValueError("report case IDs differ from current exploratory source")
    expected_keys = {
        (case_id, repetition)
        for case_id in expected_ids
        for repetition in range(1, first["repetitions"] + 1)
    }
    indexed = []
    for report in (first, second):
        by_key = {(item["case_id"], item["repetition"]): item for item in report["observations"]}
        if len(by_key) != len(report["observations"]) or set(by_key) != expected_keys:
            raise ValueError("report observations must cover each case and repetition once")
        indexed.append(by_key)

    paired_contract = {"first_only": [], "second_only": []}
    paired_action = {"first_only": [], "second_only": []}
    for case_id, repetition in sorted(expected_keys):
        left, right = (by_key[case_id, repetition] for by_key in indexed)
        key = f"{case_id}.r{repetition}"
        if left["contract_valid"] != right["contract_valid"]:
            winner = "first_only" if left["contract_valid"] else "second_only"
            paired_contract[winner].append(key)
        left_action = left["contract_valid"] and left["action_draft_match"] is True
        right_action = right["contract_valid"] and right["action_draft_match"] is True
        if left_action != right_action:
            winner = "first_only" if left_action else "second_only"
            paired_action[winner].append(key)

    by_scenario = {}
    for scenario in sorted({case["scenario_key"] for case in cases}):
        ids = {case["id"] for case in cases if case["scenario_key"] == scenario}
        by_scenario[scenario] = {
            report["model"]: summarize(
                [item for item in report["observations"] if item["case_id"] in ids]
            )
            for report in (first, second)
        }
    return {
        "kind": "exploratory_broad_ai_gguf_comparison_v1",
        "not_official_quality_score": True,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "sentence_source_sha256": first["sentence_source_sha256"],
        "field_draft_sha256": first["field_draft_sha256"],
        "code_git_commit": first["code_git_commit"],
        "implementation_sha256": first["implementation_sha256"],
        "case_count": len(cases),
        "repetitions": first["repetitions"],
        "models": [
            {
                "model": report["model"],
                "model_sha256": report["model_sha256"],
                "summary": report["summary"],
            }
            for report in (first, second)
        ],
        "paired_contract": paired_contract,
        "paired_action_draft_match": paired_action,
        "by_scenario": by_scenario,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", required=True, type=Path)
    parser.add_argument("--second", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    result = compare(json.loads(args.first.read_text()), json.loads(args.second.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
