"""Independent audit entry point for the frozen exposed A/S experiment.

No candidate or runner validation is imported.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.as_safety_v2.verify_journal import check_end, summarize
from experiments.as_safety_v2.verify_sources import (
    CASE_ORDER,
    COMMIT_RE,
    INPUTS,
    SHA_RE,
    _cases,
    _git_bytes,
    _json,
    _package_sources,
    digest,
)


def verify(protocol_path: Path, journal_path: Path, *, private_dir: Path | None = None) -> dict:
    protocol_bytes = protocol_path.read_bytes()
    protocol = _json(protocol_bytes)
    if (
        type(protocol) is not dict
        or set(protocol)
        != {
            "kind",
            "claim_scope",
            "case_order",
            "input_hashes",
            "source_manifest",
            "model_sha256",
            "server_image_digest",
            "request_policy",
            "local_runtime",
            "retry_policy",
            "private_output",
            "frozen_code_commit",
        }
        or (
            protocol["kind"] != "as_safety_extraction_v2_development_v1"
            or protocol["claim_scope"] != "already_exposed_ai_authored_a_only_development_only"
            or protocol["case_order"] != CASE_ORDER
            or protocol["retry_policy"] != "no_retry_manual_audit_on_interruption"
            or protocol["private_output"] != "outside_repository_mode_0700_files_0600"
            or protocol["server_image_digest"]
            != "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
            or protocol["local_runtime"]
            != {
                "host_port": 18081,
                "cpu_count": 2,
                "memory_bytes": 4 * 1024**3,
                "context_tokens": 4096,
                "threads": 2,
                "parallel_slots": 1,
            }
            or protocol["request_policy"]
            != {
                "max_tokens": 320,
                "temperature": 0,
                "repeat_penalty": 1.05,
                "stop": ["<|eot_id|>"],
                "timeout_seconds": 180,
                "seed": 0,
            }
            or type(protocol["frozen_code_commit"]) is not str
            or not COMMIT_RE.fullmatch(protocol["frozen_code_commit"])
            or type(protocol["model_sha256"]) is not str
            or not SHA_RE.fullmatch(protocol["model_sha256"])
        )
    ):
        raise ValueError("frozen protocol fields differ")
    commit = protocol["frozen_code_commit"]
    sources = _package_sources(commit)
    if type(protocol["source_manifest"]) is not dict or set(protocol["source_manifest"]) != sources:
        raise ValueError("frozen source manifest paths differ")
    for name, expected in protocol["source_manifest"].items():
        if expected != digest(_git_bytes(commit, name)):
            raise ValueError(f"frozen source digest differs: {name}")
    if type(protocol["input_hashes"]) is not dict or set(protocol["input_hashes"]) != set(INPUTS):
        raise ValueError("frozen input hash fields differ")
    inputs = {key: _git_bytes(commit, path) for key, path in INPUTS.items()}
    for key, raw in inputs.items():
        if protocol["input_hashes"][key] != digest(raw):
            raise ValueError(f"frozen input digest differs: {key}")
    cases = _cases(inputs)
    lines = journal_path.read_text(encoding="utf-8").splitlines()
    if len(lines) != 45:
        raise ValueError("journal row count differs")
    rows = [_json(line) for line in lines]
    if rows[0] != {"event": "header", "protocol_sha256": digest(protocol_bytes)}:
        raise ValueError("journal header differs")
    results = []
    for index, case in enumerate(cases):
        if rows[1 + 2 * index] != {"event": "begin", "case_id": case["id"]}:
            raise ValueError("journal begin row differs")
        results.append(check_end(rows[2 + 2 * index], case, private_dir))
    return {
        "claim_scope": protocol["claim_scope"],
        "historical_comparison_allowed": False,
        "raw_artifacts_verified": private_dir is not None,
        "executing_verifier_matches_frozen": digest(Path(__file__).read_bytes())
        == protocol["source_manifest"]["experiments/as_safety_v2/verify.py"],
        "exact_reference_match_is_semantic_accuracy": False,
        "summary": summarize(results),
        "per_case": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            verify(args.protocol, args.journal, private_dir=args.private_dir),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
