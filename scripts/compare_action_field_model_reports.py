"""Compare paired exploratory split probes from two pinned GGUF model files."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.probe_gguf_action_field_dev import KIND, summarize_pairs

MATCHED_SETTINGS = (
    "case_source_sha256",
    "implementation_sha256",
    "code_git_commit",
    "server_image_digest",
    "runtime",
    "container_cpu_limit",
    "server_threads",
    "context_size",
    "request_settings",
    "schema_format",
    "case_ids",
    "repetitions",
)


def compare(first: dict, second: dict) -> dict:
    for report in (first, second):
        if (
            report.get("kind") != KIND
            or report.get("not_official_quality_score") is not True
            or report.get("complete") is not True
        ):
            raise ValueError("both inputs must be complete exploratory split reports")
        pairs = report["pairs"]
        if len(pairs) != len(report["case_ids"]) * report["repetitions"]:
            raise ValueError("report has an incomplete pair grid")
        expected = {
            (case_id, repetition)
            for case_id in report["case_ids"]
            for repetition in range(1, report["repetitions"] + 1)
        }
        actual = {(pair["case_id"], pair["repetition"]) for pair in pairs}
        if actual != expected or len(pairs) != len(actual):
            raise ValueError("report pair IDs or repetitions are inconsistent")
        if summarize_pairs(pairs) != report["summary"]:
            raise ValueError("report summary does not match observations")
    for key in MATCHED_SETTINGS:
        if first[key] != second[key]:
            raise ValueError(f"model reports must share {key}")
    if [(pair["case_id"], pair["repetition"], pair["order"]) for pair in first["pairs"]] != [
        (pair["case_id"], pair["repetition"], pair["order"]) for pair in second["pairs"]
    ]:
        raise ValueError("model reports must have identical pair order")
    if first["model_sha256"] == second["model_sha256"]:
        raise ValueError("model files must differ for model comparison")
    return {
        "kind": "exploratory_action_field_model_comparison_v1",
        "not_official_quality_score": True,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "case_source_sha256": first["case_source_sha256"],
        "implementation_sha256": first["implementation_sha256"],
        "code_git_commit": first["code_git_commit"],
        "case_ids": first["case_ids"],
        "repetitions": first["repetitions"],
        "model_results": [
            {"model": report["model"], "model_sha256": report["model_sha256"], **report["summary"]}
            for report in (first, second)
        ],
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
