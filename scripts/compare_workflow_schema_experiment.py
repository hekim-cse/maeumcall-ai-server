"""Compare a workflow-schema probe with the same model's plain GGUF baseline.

Only matched AI draft cases are counted. These are diagnostic contract and
draft-label agreement counts, not human-adjudicated accuracy.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.compare_exploratory_gguf_reports import KIND, _draft_match, _load


def compare(baseline: dict, constrained: dict) -> dict:
    if baseline.get("kind") != KIND or constrained.get("kind") != KIND:
        raise ValueError("both inputs must be round-two exploratory reports")
    if baseline.get("complete") is not True or constrained.get("complete") is not True:
        raise ValueError("both reports must be complete")
    if baseline.get("workflow_schema_constrained", False) or not constrained.get(
        "workflow_schema_constrained", False
    ):
        raise ValueError("expected plain baseline and constrained candidate")
    for key in (
        "sentence_draft_sha256",
        "label_draft_sha256",
        "model_sha256",
        "server_image_digest",
        "runtime",
        "container_cpu_limit",
        "server_threads",
        "context_size",
        "request_settings",
    ):
        if baseline[key] != constrained[key]:
            raise ValueError(f"paired conditions must share {key}")
    baseline_by_id = {item["case_id"]: item for item in baseline["observations"]}
    case_ids = constrained["selected_case_ids"]
    if len(case_ids) != len(set(case_ids)) or not set(case_ids) <= set(baseline_by_id):
        raise ValueError("constrained cases must be unique baseline cases")
    if [item["case_id"] for item in constrained["observations"]] != case_ids:
        raise ValueError("constrained report cases are inconsistent")
    plain = [baseline_by_id[case_id] for case_id in case_ids]
    restricted = constrained["observations"]
    return {
        "kind": "exploratory_workflow_schema_comparison_v1",
        "not_official_quality_score": True,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "model_sha256": baseline["model_sha256"],
        "sentence_draft_sha256": baseline["sentence_draft_sha256"],
        "label_draft_sha256": baseline["label_draft_sha256"],
        "schema_format": constrained["schema_format"],
        "case_count": len(case_ids),
        "case_ids": case_ids,
        "plain_contract_passes": sum(item["contract_valid"] is True for item in plain),
        "constrained_contract_passes": sum(item["contract_valid"] is True for item in restricted),
        "plain_draft_matches": sum(_draft_match(item) for item in plain),
        "constrained_draft_matches": sum(_draft_match(item) for item in restricted),
        "new_contract_pass_case_ids": [
            case_id
            for case_id, left, right in zip(case_ids, plain, restricted, strict=True)
            if left["contract_valid"] is False and right["contract_valid"] is True
        ],
        "lost_contract_pass_case_ids": [
            case_id
            for case_id, left, right in zip(case_ids, plain, restricted, strict=True)
            if left["contract_valid"] is True and right["contract_valid"] is False
        ],
        "new_draft_match_case_ids": [
            case_id
            for case_id, left, right in zip(case_ids, plain, restricted, strict=True)
            if not _draft_match(left) and _draft_match(right)
        ],
        "lost_draft_match_case_ids": [
            case_id
            for case_id, left, right in zip(case_ids, plain, restricted, strict=True)
            if _draft_match(left) and not _draft_match(right)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--constrained", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")
    result = compare(_load(args.baseline), _load(args.constrained))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        f"contract={result['plain_contract_passes']}->{result['constrained_contract_passes']} "
        f"draft_match={result['plain_draft_matches']}->{result['constrained_draft_matches']}"
    )


if __name__ == "__main__":
    main()
