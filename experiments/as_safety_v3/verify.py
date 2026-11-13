"""Independently audit the paired, development-only A/S Stage2 experiment.

This module never imports the candidate relation or runner decision functions.
Anchored quotations establish provenance, not the truth of an entity relation.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path

from experiments.as_safety_v2 import verify_journal as baseline_audit
from experiments.as_safety_v2 import verify_sources as source

ROOT = Path(__file__).resolve().parents[2]
DATA = "evals/structured_nlu/data/ai_heldout/"
BASELINE_PROTOCOL = DATA + "as-safety-extraction-v2-development-protocol.v1.json"
BASELINE_JOURNAL = DATA + "as-safety-extraction-v2-development-journal.v1.jsonl"
INPUTS = source.INPUTS | {
    "baseline_protocol": BASELINE_PROTOCOL,
    "baseline_journal": BASELINE_JOURNAL,
}
KIND = "as_safety_owner_link_v3_stage2_paired_v1"
SCOPE = "already_exposed_ai_authored_conditional_stage2_development_only"
IMAGE = "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
MODEL_SHA = "644b04cde835d486df33c6d4d7552ba367fcb28802fe39b6b4bb9c60b9ab6f3d"
RUNTIME = {
    "host_port": 18081,
    "cpu_count": 2,
    "memory_bytes": 4 * 1024**3,
    "context_tokens": 4096,
    "threads": 2,
    "parallel_slots": 1,
}
POLICY = {
    "max_tokens": 320,
    "temperature": 0,
    "repeat_penalty": 1.05,
    "stop": ["<|eot_id|>"],
    "timeout_seconds": 180,
    "seed": 0,
}
PROTOCOL_KEYS = {
    "kind",
    "claim_scope",
    "case_order",
    "frozen_code_commit",
    "input_hashes",
    "source_manifest",
    "model_sha256",
    "server_image_digest",
    "request_policy",
    "local_runtime",
    "retry_policy",
    "private_output",
}
END_KEYS = {
    "event",
    "case_id",
    "baseline_stage1",
    "stage2",
    "source_relation",
    "stage2_elapsed_ms",
}
STAGE2_KEYS = {
    "called",
    "status",
    "skip_reason",
    "error_code",
    "error_field",
    "finish_reason",
    "latency_ms",
    "raw_sha256",
    "raw_bytes",
    "model_link",
    "effective_relation",
    "hazard_owner_span",
}
LINKS = {
    "same": "current",
    "part_of": "current",
    "coreference": "current",
    "distinct": "other",
    "unclear": "unknown",
}
TRANSPORT_ERRORS = baseline_audit.TRANSPORT_ERRORS
CONTRACT_ERRORS = {
    "fields_invalid",
    "link_invalid",
    "owner_required",
    "duplicate_key",
    "nonfinite_number",
    "invalid_json",
    "response_type_invalid",
    "quote_fields_invalid",
    "quote_index_invalid",
    "quote_type_invalid",
    "quote_blank",
    "quote_unanchored",
    "quote_nonunique",
    "stage1_fields_invalid",
    "stage1_incomplete",
    "stage1_span_invalid",
}
CONTRACT_FIELDS = {
    "$",
    "stage1",
    "stage2",
    "event_span",
    "subject_span",
    "owner_to_target",
    "hazard_owner_span",
}
PAIRS = (("V01", "V02"), ("V05", "V06"), ("V07", "V08"))


def _number(value: object) -> bool:
    return type(value) in {int, float} and math.isfinite(value) and 0 <= value < 86_400_000


def _git(commit: str, relative: str) -> bytes:
    return source._git_bytes(commit, relative)


def _source_paths(commit: str) -> set[str]:
    if not source.COMMIT_RE.fullmatch(commit):
        raise ValueError("frozen commit differs")
    output = subprocess.run(
        (
            "git",
            "ls-tree",
            "-r",
            "--name-only",
            commit,
            "--",
            "experiments/as_safety_v2",
            "experiments/as_safety_v3",
        ),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    paths = {line for line in output.splitlines() if line.endswith(".py")}
    if (
        not {
            "experiments/as_safety_v3/relation.py",
            "experiments/as_safety_v3/run.py",
            "experiments/as_safety_v3/verify.py",
            "experiments/as_safety_v2/run.py",
            "experiments/as_safety_v2/verify.py",
            "experiments/as_safety_v2/verify_journal.py",
        }
        <= paths
    ):
        raise ValueError("frozen source package incomplete")
    return paths


def _protocol(protocol_path: Path, model_path: Path | None = None) -> tuple[dict, dict[str, bytes]]:
    payload = protocol_path.read_bytes()
    protocol = source._json(payload)
    if type(protocol) is not dict or set(protocol) != PROTOCOL_KEYS:
        raise ValueError("protocol fields differ")
    commit = protocol["frozen_code_commit"]
    if (
        protocol["kind"] != KIND
        or protocol["claim_scope"] != SCOPE
        or protocol["case_order"] != source.CASE_ORDER
        or type(commit) is not str
        or not source.COMMIT_RE.fullmatch(commit)
        or protocol["server_image_digest"] != IMAGE
        or protocol["request_policy"] != POLICY
        or protocol["local_runtime"] != RUNTIME
        or protocol["retry_policy"] != "no_retry_manual_audit_on_interruption"
        or protocol["private_output"] != "outside_repository_mode_0700_files_0600"
        or protocol["model_sha256"] != MODEL_SHA
    ):
        raise ValueError("protocol identity differs")
    if (
        model_path is not None
        and source.digest(model_path.read_bytes()) != protocol["model_sha256"]
    ):
        raise ValueError("model digest differs")
    relative = protocol_path.resolve().relative_to(ROOT).as_posix()
    committed_protocol = subprocess.run(
        ("git", "show", f"HEAD:{relative}"),
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    if committed_protocol != payload:
        raise ValueError("committed protocol differs")
    manifest = protocol["source_manifest"]
    if type(manifest) is not dict or set(manifest) != _source_paths(commit):
        raise ValueError("source manifest paths differ")
    for name, expected in manifest.items():
        frozen = _git(commit, name)
        if (
            type(expected) is not str
            or not source.SHA_RE.fullmatch(expected)
            or source.digest(frozen) != expected
            or (ROOT / name).read_bytes() != frozen
        ):
            raise ValueError(f"source manifest differs: {name}")
    hashes = protocol["input_hashes"]
    if type(hashes) is not dict or set(hashes) != set(INPUTS):
        raise ValueError("input manifest paths differ")
    inputs = {}
    for key, name in INPUTS.items():
        frozen = _git(commit, name)
        if (
            type(hashes[key]) is not str
            or not source.SHA_RE.fullmatch(hashes[key])
            or source.digest(frozen) != hashes[key]
            or (ROOT / name).read_bytes() != frozen
        ):
            raise ValueError(f"input manifest differs: {key}")
        inputs[key] = frozen
    return protocol, inputs


def _baseline(inputs: dict[str, bytes], old_private_dir: Path) -> tuple[list[dict], list[dict]]:
    if old_private_dir.resolve().is_relative_to(ROOT) or old_private_dir.stat().st_mode & 0o077:
        raise ValueError("baseline private directory boundary differs")
    cases = source._cases(inputs)
    old_protocol = source._json(inputs["baseline_protocol"])
    if (
        type(old_protocol) is not dict
        or old_protocol.get("kind") != "as_safety_extraction_v2_development_v1"
    ):
        raise ValueError("baseline protocol differs")
    lines = inputs["baseline_journal"].splitlines()
    if len(lines) != 45:
        raise ValueError("baseline journal row count differs")
    rows = [source._json(line) for line in lines]
    if rows[0] != {
        "event": "header",
        "protocol_sha256": source.digest(inputs["baseline_protocol"]),
    }:
        raise ValueError("baseline journal header differs")
    ends = []
    for index, case in enumerate(cases):
        if rows[1 + 2 * index] != {"event": "begin", "case_id": case["id"]}:
            raise ValueError("baseline journal order differs")
        end = rows[2 + 2 * index]
        baseline_audit.check_end(end, case)
        raw_path = old_private_dir / f"{case['id']}-stage1.json.txt"
        if raw_path.stat().st_mode & 0o077:
            raise ValueError("baseline raw file permissions differ")
        baseline_audit._check_stage1(end["stage1"], case, old_private_dir)
        ends.append(end)
    if sum(end["stage1"]["status"] == "validated" for end in ends) != 20:
        raise ValueError("baseline Stage1 denominator differs")
    return cases, ends


def _raw_stage2(raw: str, clauses: tuple[str, ...]) -> tuple[str, str, dict | None]:
    parsed = source._json(raw)
    if type(parsed) is not dict or set(parsed) != {"owner_to_target", "hazard_owner_span"}:
        raise source.ContractError("fields_invalid", "stage2")
    link = parsed["owner_to_target"]
    if type(link) is not str or link not in LINKS:
        raise source.ContractError("link_invalid", "owner_to_target")
    span = baseline_audit._raw_span(parsed["hazard_owner_span"], clauses, "hazard_owner_span")
    if link != "unclear" and span is None:
        raise source.ContractError("owner_required", "hazard_owner_span")
    return link, LINKS[link], span


def _raw_meta(stage: dict, private_dir: Path | None, case_id: str) -> str | None:
    sha, size = stage["raw_sha256"], stage["raw_bytes"]
    if sha is None:
        if size is not None:
            raise ValueError("raw metadata differs")
        return None
    if (
        type(sha) is not str
        or not source.SHA_RE.fullmatch(sha)
        or type(size) is not int
        or not 0 <= size <= 1_000_000
    ):
        raise ValueError("raw metadata differs")
    if private_dir is None:
        return None
    raw_path = private_dir / f"{case_id}-stage2.json.txt"
    if raw_path.stat().st_mode & 0o077:
        raise ValueError("candidate raw file permissions differ")
    raw = raw_path.read_bytes()
    if len(raw) != size or source.digest(raw) != sha:
        raise ValueError("private Stage2 raw differs")
    return raw.decode("utf-8")


def _check_end(row: object, case: dict, old: dict, private_dir: Path | None) -> dict:
    if (
        type(row) is not dict
        or set(row) != END_KEYS
        or row["event"] != "end"
        or row["case_id"] != case["id"]
        or row["baseline_stage1"] != old["stage1"]
        or type(row["stage2"]) is not dict
        or set(row["stage2"]) != STAGE2_KEYS
    ):
        raise ValueError("paired journal end row differs")
    stage = row["stage2"]
    called = old["stage1"]["status"] == "validated" and all(
        old["stage1"]["spans"][field] is not None for field in ("event_span", "subject_span")
    )
    if stage["called"] is not called:
        raise ValueError("Stage2 call transition differs")
    if not called:
        if row["stage2_elapsed_ms"] is not None:
            raise ValueError("skipped Stage2 elapsed time differs")
        expected = {
            "called": False,
            "status": "skipped",
            "skip_reason": "baseline_stage1_invalid",
            **{key: None for key in STAGE2_KEYS - {"called", "status", "skip_reason"}},
        }
        if stage != expected or row["source_relation"] != "unknown":
            raise ValueError("Stage2 skip state differs")
    else:
        if (
            stage["status"] not in {"validated", "contract_error", "response_error"}
            or stage["skip_reason"] is not None
            or not _number(stage["latency_ms"])
            or not _number(row["stage2_elapsed_ms"])
        ):
            raise ValueError("Stage2 status or latency differs")
        if row["stage2_elapsed_ms"] + 0.01 < stage["latency_ms"]:
            raise ValueError("Stage2 elapsed time differs")
        raw = _raw_meta(stage, private_dir, case["id"])
        if stage["finish_reason"] not in {None, "stop", "length"}:
            raise ValueError("Stage2 finish reason differs")
        if stage["status"] == "validated":
            if (
                stage["finish_reason"] != "stop"
                or stage["raw_sha256"] is None
                or stage["error_code"] is not None
                or stage["error_field"] is not None
                or stage["model_link"] not in LINKS
                or stage["effective_relation"] != LINKS[stage["model_link"]]
            ):
                raise ValueError("validated Stage2 metadata differs")
            span = baseline_audit._span(stage["hazard_owner_span"], case["clauses"])
            if stage["model_link"] != "unclear" and span is None:
                raise ValueError("validated Stage2 owner missing")
            if raw is not None and _raw_stage2(raw, case["clauses"]) != (
                stage["model_link"],
                stage["effective_relation"],
                span,
            ):
                raise ValueError("Stage2 raw decision differs")
        else:
            if any(
                stage[key] is not None
                for key in ("model_link", "effective_relation", "hazard_owner_span")
            ):
                raise ValueError("failed Stage2 has accepted decision")
            code = stage["error_code"]
            if type(code) is not str or not source.ERROR_RE.fullmatch(code):
                raise ValueError("Stage2 error code differs")
            if stage["status"] == "contract_error":
                if (
                    code not in CONTRACT_ERRORS
                    or type(stage["error_field"]) is not str
                    or stage["error_field"] not in CONTRACT_FIELDS
                    or stage["finish_reason"] != "stop"
                    or stage["raw_sha256"] is None
                ):
                    raise ValueError("Stage2 contract error metadata differs")
                if raw is not None:
                    try:
                        _raw_stage2(raw, case["clauses"])
                    except source.ContractError as error:
                        if (error.code, error.field) != (code, stage["error_field"]):
                            raise ValueError("Stage2 raw error differs") from error
                    else:
                        raise ValueError("Stage2 raw unexpectedly valid")
            else:
                if stage["error_field"] is not None:
                    raise ValueError("Stage2 response error field differs")
                if code == "finish_length":
                    if stage["finish_reason"] != "length" or stage["raw_sha256"] is None:
                        raise ValueError("Stage2 length metadata differs")
                elif code in TRANSPORT_ERRORS:
                    if stage["finish_reason"] is not None or stage["raw_sha256"] is not None:
                        raise ValueError("Stage2 transport metadata differs")
                else:
                    raise ValueError("Stage2 transport code differs")
        expected_relation = (
            stage["effective_relation"] if stage["status"] == "validated" else "unknown"
        )
        if row["source_relation"] != expected_relation:
            raise ValueError("source relation differs")
    baseline_relation = (
        old["stage2"]["effective_relation"] if old["stage2"]["status"] == "validated" else "unknown"
    )
    return {
        "id": case["id"],
        "gold_relation": case["relation"],
        "event_status": case["event_status"],
        "eligible": called,
        "baseline_relation": baseline_relation,
        "candidate_relation": row["source_relation"],
        "baseline_error": old["stage2"]["status"] != "validated" if called else False,
        "candidate_error": stage["status"] != "validated" if called else False,
        "model_link": stage["model_link"],
        "stage2_latency_ms": stage["latency_ms"],
    }


def _aggregate(rows: list[dict], key: str) -> dict:
    eligible = [row for row in rows if row["eligible"]]
    by_id = {row["id"]: row for row in eligible}
    current = [row for row in eligible if row["gold_relation"] == "current"]
    observed = [row for row in current if row["event_status"] == "observed"]
    other = [row for row in eligible if row["gold_relation"] == "other"]
    pairs = sum(
        all(by_id[item][key] == gold for item, gold in zip(pair, ("current", "other"), strict=True))
        and not any(
            by_id[item]["candidate_error" if key == "candidate_relation" else "baseline_error"]
            for item in pair
        )
        for pair in PAIRS
    )
    return {
        "denominator": len(eligible),
        "relation_correct": sum(row[key] == row["gold_relation"] for row in eligible),
        "current": {
            "correct": sum(row[key] == "current" for row in current),
            "denominator": len(current),
        },
        "observed_current": {
            "correct": sum(row[key] == "current" for row in observed),
            "denominator": len(observed),
        },
        "other": {"correct": sum(row[key] == "other" for row in other), "denominator": len(other)},
        "contrast_pairs": {"recovered": pairs, "denominator": len(PAIRS)},
        "errors": sum(
            row["candidate_error" if key == "candidate_relation" else "baseline_error"]
            for row in eligible
        ),
    }


def verify(
    protocol_path: Path,
    journal_path: Path,
    *,
    old_private_dir: Path,
    private_dir: Path | None = None,
    model_path: Path | None = None,
) -> dict:
    """Verify frozen sources, both raw streams, all transitions and paired metrics."""
    if private_dir is not None and (
        private_dir.resolve().is_relative_to(ROOT) or private_dir.stat().st_mode & 0o077
    ):
        raise ValueError("candidate private directory boundary differs")
    protocol, inputs = _protocol(protocol_path, model_path)
    cases, old_ends = _baseline(inputs, old_private_dir)
    rows = [source._json(line) for line in journal_path.read_bytes().splitlines()]
    if len(rows) != 45 or rows[0] != {
        "event": "header",
        "protocol_sha256": source.digest(protocol_path.read_bytes()),
    }:
        raise ValueError("paired journal header or row count differs")
    results = []
    for index, (case, old) in enumerate(zip(cases, old_ends, strict=True)):
        if rows[1 + 2 * index] != {"event": "begin", "case_id": case["id"]}:
            raise ValueError("paired journal order differs")
        results.append(_check_end(rows[2 + 2 * index], case, old, private_dir))
    if sum(row["eligible"] for row in results) != 20:
        raise ValueError("conditional denominator differs")
    baseline = _aggregate(results, "baseline_relation")
    candidate = _aggregate(results, "candidate_relation")
    if (
        candidate["current"]["denominator"],
        candidate["observed_current"]["denominator"],
        candidate["other"]["denominator"],
    ) != (14, 12, 6):
        raise ValueError("reviewed subgroup denominator differs")
    gate_passed = (
        private_dir is not None
        and candidate["current"]["correct"] == 14
        and candidate["observed_current"]["correct"] == 12
        and candidate["other"]["correct"] == 6
        and candidate["contrast_pairs"]["recovered"] == 3
        and candidate["errors"] == 0
    )
    return {
        "claim_scope": protocol["claim_scope"],
        "total_cases": len(results),
        "baseline_stage1_valid": sum(row["eligible"] for row in results),
        "baseline_stage1_failures": sum(not row["eligible"] for row in results),
        "raw_baseline_stage1_verified": True,
        "raw_candidate_stage2_verified": private_dir is not None,
        "same_20_case_baseline": baseline,
        "same_20_case_candidate": candidate,
        "conditional_stage2_gate_passed": gate_passed,
        "full_22_case_safety_gate_possible": False,
        "historical_improvement_or_official_accuracy_allowed": False,
        "per_case": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--old-private-dir", required=True, type=Path)
    parser.add_argument("--private-dir", required=True, type=Path)
    parser.add_argument("--model", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            verify(
                args.protocol,
                args.journal,
                old_private_dir=args.old_private_dir,
                private_dir=args.private_dir,
                model_path=args.model,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
