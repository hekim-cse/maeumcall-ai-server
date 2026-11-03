"""Compare two completed GGUF probes on identical AI-assisted draft cases.

The result is a diagnostic agreement comparison with unadjudicated draft labels,
never an official accuracy or improvement score.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

KIND = "exploratory_gguf_review_draft_round2_v1"


def _load(path: Path) -> dict:
    report = json.loads(path.read_text())
    if report.get("kind") != KIND or report.get("not_official_quality_score") is not True:
        raise ValueError(f"not a round-two exploratory report: {path}")
    if report.get("complete") is not True:
        raise ValueError(f"incomplete exploratory report: {path}")
    case_ids = report.get("selected_case_ids")
    observations = report.get("observations")
    if (
        not isinstance(case_ids, list)
        or not isinstance(observations, list)
        or len(case_ids) != report.get("case_count")
        or len(case_ids) != len(observations)
        or len(set(case_ids)) != len(case_ids)
        or [item.get("case_id") for item in observations] != case_ids
    ):
        raise ValueError(f"report cases are inconsistent: {path}")
    return report


def _draft_match(observation: dict) -> bool:
    if observation.get("contract_valid") is False:
        return False
    if observation.get("contract_valid") is not True:
        raise ValueError("observation is missing contract_valid")
    mismatches = observation.get("draft_label_mismatch_fields")
    if not isinstance(mismatches, list):
        raise ValueError("valid observation is missing draft mismatches")
    return not mismatches


def compare(baseline: dict, candidate: dict) -> dict:
    for key in ("workflow_schema_constrained", "schema_format"):
        if baseline.get(key) != candidate.get(key):
            raise ValueError(f"paired reports must share {key}")
    for key in (
        "sentence_draft_sha256",
        "label_draft_sha256",
        "request_settings",
        "selected_case_ids",
        "server_image_digest",
        "runtime",
        "container_cpu_limit",
        "server_threads",
        "context_size",
    ):
        if baseline[key] != candidate[key]:
            raise ValueError(f"paired reports must share {key}")
    baseline_results = {item["case_id"]: _draft_match(item) for item in baseline["observations"]}
    candidate_results = {item["case_id"]: _draft_match(item) for item in candidate["observations"]}
    case_ids = baseline["selected_case_ids"]
    improved = [
        case_id
        for case_id in case_ids
        if not baseline_results[case_id] and candidate_results[case_id]
    ]
    regressed = [
        case_id
        for case_id in case_ids
        if baseline_results[case_id] and not candidate_results[case_id]
    ]
    return {
        "kind": "exploratory_gguf_pairwise_draft_comparison_v1",
        "not_official_quality_score": True,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "sentence_draft_sha256": baseline["sentence_draft_sha256"],
        "label_draft_sha256": baseline["label_draft_sha256"],
        "case_count": len(case_ids),
        "baseline_model_sha256": baseline["model_sha256"],
        "candidate_model_sha256": candidate["model_sha256"],
        "baseline_contract_passes": sum(
            item["contract_valid"] is True for item in baseline["observations"]
        ),
        "candidate_contract_passes": sum(
            item["contract_valid"] is True for item in candidate["observations"]
        ),
        "baseline_draft_matches": sum(baseline_results.values()),
        "candidate_draft_matches": sum(candidate_results.values()),
        "draft_match_delta_cases": len(improved) - len(regressed),
        "improved_case_ids": improved,
        "regressed_case_ids": regressed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")

    result = compare(_load(args.baseline), _load(args.candidate))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        f"draft_matches={result['baseline_draft_matches']}->{result['candidate_draft_matches']} "
        f"cases={result['case_count']} output={args.output}"
    )


if __name__ == "__main__":
    main()
