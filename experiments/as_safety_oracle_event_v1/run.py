"""Run a frozen local Stage2-only diagnostic on reviewed ES events.

Only the utterance, reviewed target and event span/occurrence enter prompts.
Reviewed owner, relation and route are used solely after calls for scoring.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import stat
import statistics
import time
from pathlib import Path

from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.transport import RequestPolicy, post_json_completion
from experiments.as_safety_v4 import run as v4
from experiments.as_safety_v4.cases import load_cases
from experiments.as_safety_v4.contract import (
    route_for_events,
    stage2_messages,
    stage2_schema,
    validate_stage2,
)

ROOT = v4.ROOT
KIND = "as_safety_oracle_event_v1_exploration_v1"
SCOPE = "already_exposed_ai_authored_oracle_event_conditional_development_only"
CASE_ORDER = v4.CASE_ORDER
IMAGE = v4.IMAGE
MODEL_SHA = v4.MODEL_SHA
RUNTIME = v4.RUNTIME
REQUEST = v4.REQUEST
INPUTS = {
    "dataset": v4.INPUTS["dataset"],
    "review": v4.INPUTS["review"],
    "field_review": v4.INPUTS["field_review"],
    "method": ROOT / "docs/portfolio/nlu_safety_oracle_event_v1_method.md",
}
PROTOCOL_FIELDS = v4.PROTOCOL_FIELDS
REQUIRED_SOURCES = v4.REQUIRED_V4_SOURCES | {
    "experiments/as_safety_oracle_event_v1/__init__.py",
    "experiments/as_safety_oracle_event_v1/run.py",
    "experiments/as_safety_oracle_event_v1/verify.py",
}
CompletionCall = v4.CompletionCall
RELATION_CATEGORIES = (
    "observed_current",
    "observed_other",
    "observed_unknown",
    "uncertain_current",
)
CONTRAST_PAIRS = (("ES01", "ES09"), ("ES02", "ES11"))


def _source_paths(commit: str) -> set[str]:
    paths = set()
    for prefix in (
        "experiments/as_safety_v2",
        "experiments/as_safety_v4",
        "experiments/as_safety_oracle_event_v1",
    ):
        output = v4._git("ls-tree", "-r", "--name-only", commit, "--", prefix)
        paths.update(path for path in output.decode().splitlines() if path.endswith(".py"))
    return paths


def load_protocol(path: Path, model_path: Path) -> tuple[dict, str]:
    """Match committed protocol, entire dependency source, inputs and model."""
    raw = path.read_bytes()
    protocol = json.loads(raw)
    if type(protocol) is not dict or set(protocol) != PROTOCOL_FIELDS:
        raise ValueError("protocol fields differ")
    commit = protocol["frozen_code_commit"]
    if (
        type(commit) is not str
        or re.fullmatch(r"[0-9a-f]{40}", commit) is None
        or protocol["kind"] != KIND
        or protocol["claim_scope"] != SCOPE
        or protocol["case_order"] != list(CASE_ORDER)
        or protocol["server_image_digest"] != IMAGE
        or protocol["model_sha256"] != MODEL_SHA
        or v4.digest_file(model_path) != MODEL_SHA
        or protocol["request_policy"] != REQUEST
        or protocol["local_runtime"] != RUNTIME
        or protocol["retry_policy"] != "no_retry_manual_audit_on_interruption"
        or protocol["private_output"] != "outside_repository_mode_0700_files_0600"
    ):
        raise ValueError("protocol identity differs")
    hashes = protocol["input_hashes"]
    if type(hashes) is not dict or set(hashes) != set(INPUTS):
        raise ValueError("input manifest differs")
    for key, input_path in INPUTS.items():
        relative = input_path.relative_to(ROOT).as_posix()
        frozen = v4._committed(commit, relative)
        expected = hashes[key]
        if type(expected) is not str or v4.SHA_RE.fullmatch(expected) is None:
            raise ValueError(f"input hash differs: {key}")
        if v4.digest(frozen) != expected or frozen != input_path.read_bytes():
            raise ValueError(f"frozen input differs: {key}")
    sources = _source_paths(commit)
    if not REQUIRED_SOURCES <= sources:
        raise ValueError("required oracle source missing from frozen commit")
    manifest = protocol["source_manifest"]
    if type(manifest) is not dict or set(manifest) != sources:
        raise ValueError("source manifest differs")
    for relative, expected in manifest.items():
        if type(expected) is not str or v4.SHA_RE.fullmatch(expected) is None:
            raise ValueError(f"source hash differs: {relative}")
        frozen = v4._committed(commit, relative)
        if v4.digest(frozen) != expected or frozen != (ROOT / relative).read_bytes():
            raise ValueError(f"frozen source differs: {relative}")
    try:
        relative_protocol = path.resolve().relative_to(ROOT).as_posix()
    except ValueError as error:
        raise ValueError("protocol must be in repository") from error
    if v4._git("show", f"HEAD:{relative_protocol}") != raw:
        raise ValueError("protocol must be committed before model calls")
    if v4._git("rev-parse", "HEAD").decode().strip() != commit:
        raise ValueError("frozen commit is not HEAD")
    if v4._git("status", "--porcelain").strip():
        raise ValueError("checkout differs before model calls")
    return protocol, v4.digest(raw)


def call_case(
    case: dict,
    policy: RequestPolicy,
    private_dir: Path,
    *,
    completion_call: CompletionCall = post_json_completion,
) -> dict:
    """One model call per reviewed actionable event; no gold owner leakage."""
    started = time.perf_counter()
    message = case["user_message"]
    args = {
        "product_index": case["target"]["clause_index"],
        "target_mention": case["target"]["quote"],
    }
    clauses = split_clauses(message)
    stages: list[dict] = []
    route_events: list[dict] = []
    relations: list[str | None] = []
    failed = False
    for index, gold in enumerate(case["events"], 1):
        event = {
            "event_span": anchor_span(gold["event_span"], clauses, field="event_span"),
            "occurrence": gold["occurrence"],
        }
        route_events.append(event)
        public = {
            "event_index": index,
            "event_span": v4._public_span(event["event_span"]),
            "occurrence": event["occurrence"],
            "owner_to_target": None,
            "hazard_owner_span": None,
        }
        if event["occurrence"] == "nonoccurring":
            stage = v4._blank(called=False, skip_reason="nonoccurring")
            stages.append({**stage, **public})
            relations.append(None)
            continue
        stage, raw = v4._call(
            messages=stage2_messages(message, event, **args),
            schema=stage2_schema(message),
            policy=policy,
            raw_path=private_dir / f"{case['id']}-stage2-{index}.json.txt",
            completion_call=completion_call,
        )
        stage.update(public)
        if stage["error_code"] is None and raw is not None:
            try:
                decision = validate_stage2(raw, message, event, **args)
            except ValidationError as error:
                stage.update(
                    status="contract_error", error_code=error.code, error_field=error.field
                )
            else:
                stage.update(
                    status="validated",
                    owner_to_target=decision["owner_to_target"],
                    hazard_owner_span=v4._public_span(decision["hazard_owner_span"]),
                )
        if stage["status"] != "validated":
            failed = True
        stages.append(stage)
        relations.append(stage["owner_to_target"])
    route = route_for_events(route_events, relations, overflow=case["overflow"], failed=failed)
    return {
        "event": "end",
        "case_id": case["id"],
        "stage2": stages,
        "route": route,
        "request_count": sum(int(stage["called"]) for stage in stages),
        "model_call_latency_sum_ms": round(
            sum(stage["request_latency_ms"] or 0 for stage in stages), 3
        ),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def summarize(rows: list[dict], cases: list[dict]) -> dict:
    if len(rows) != len(cases) or tuple(row["case_id"] for row in rows) != tuple(
        case["id"] for case in cases
    ):
        raise ValueError("case count or order differs")
    elapsed = sorted(row["elapsed_ms"] for row in rows)
    request_latency = sorted(
        stage["request_latency_ms"] for row in rows for stage in row["stage2"] if stage["called"]
    )
    normal = "collecting_service_request"
    category_counts = dict.fromkeys(RELATION_CATEGORIES, 0)
    category_relation_correct = dict.fromkeys(RELATION_CATEGORIES, 0)
    owner_exact_correct = 0
    case_relation_correct = {}
    for row, case in zip(rows, cases, strict=True):
        clauses = split_clauses(case["user_message"])
        all_correct = True
        for stage, gold in zip(row["stage2"], case["events"], strict=True):
            if gold["occurrence"] == "nonoccurring":
                continue
            category = f"{gold['occurrence']}_{gold['owner_to_target']}"
            if category not in category_counts:
                raise ValueError("gold relation category differs")
            category_counts[category] += 1
            correct = (
                stage["status"] == "validated"
                and stage["owner_to_target"] == gold["owner_to_target"]
            )
            category_relation_correct[category] += correct
            all_correct &= correct
            gold_owner = anchor_span(gold["hazard_owner_span"], clauses, field="hazard_owner_span")
            owner_exact_correct += stage["status"] == "validated" and stage[
                "hazard_owner_span"
            ] == v4._public_span(gold_owner)
        case_relation_correct[case["id"]] = all_correct
    case_routes_correct = {
        case["id"]: row["route"] == case["expected_route"]
        for row, case in zip(rows, cases, strict=True)
    }
    eligible_pairs = [
        pair for pair in CONTRAST_PAIRS if all(case_id in case_routes_correct for case_id in pair)
    ]
    contrast_pairs_correct = sum(
        all(case_relation_correct[case_id] and case_routes_correct[case_id] for case_id in pair)
        for pair in eligible_pairs
    )
    return {
        "cases": len(rows),
        "gold_event_count": sum(len(case["events"]) for case in cases),
        "actionable_gold_event_count": sum(
            gold["occurrence"] != "nonoccurring" for case in cases for gold in case["events"]
        ),
        "relation_correct": sum(
            stage["status"] == "validated" and stage["owner_to_target"] == gold["owner_to_target"]
            for row, case in zip(rows, cases, strict=True)
            for stage, gold in zip(row["stage2"], case["events"], strict=True)
            if gold["occurrence"] != "nonoccurring"
        ),
        "owner_exact_correct": owner_exact_correct,
        "category_counts": category_counts,
        "category_relation_correct": category_relation_correct,
        "route_correct": sum(
            row["route"] == case["expected_route"] for row, case in zip(rows, cases, strict=True)
        ),
        "model_involved_cases": sum(row["request_count"] > 0 for row in rows),
        "model_involved_route_correct": sum(
            row["request_count"] > 0 and row["route"] == case["expected_route"]
            for row, case in zip(rows, cases, strict=True)
        ),
        "multi_event_cases": sum(len(case["events"]) > 1 for case in cases),
        "multi_event_route_correct": sum(
            len(case["events"]) > 1 and row["route"] == case["expected_route"]
            for row, case in zip(rows, cases, strict=True)
        ),
        "contrast_pair_count": len(eligible_pairs),
        "contrast_pairs_correct": contrast_pairs_correct,
        "other_observed_cases": sum(
            case["expected_route"] == normal
            and any(
                gold["occurrence"] == "observed" and gold["owner_to_target"] == "other"
                for gold in case["events"]
            )
            for case in cases
        ),
        "false_direct_other": sum(
            row["route"] == "safety_action_required"
            and case["expected_route"] == normal
            and any(
                gold["occurrence"] == "observed" and gold["owner_to_target"] == "other"
                for gold in case["events"]
            )
            for row, case in zip(rows, cases, strict=True)
        ),
        "missed_direct_current": sum(
            case["expected_route"] == "safety_action_required"
            and row["route"] != "safety_action_required"
            for row, case in zip(rows, cases, strict=True)
        ),
        "unnecessary_confirm": sum(
            case["expected_route"] == normal and row["route"] == "confirming_safety_status"
            for row, case in zip(rows, cases, strict=True)
        ),
        "stage2_errors": sum(
            stage["called"] and stage["status"] != "validated"
            for row in rows
            for stage in row["stage2"]
        ),
        "request_count": sum(row["request_count"] for row in rows),
        "stage2_valid": sum(
            stage["status"] == "validated" for row in rows for stage in row["stage2"]
        ),
        "case_elapsed_p50_ms": round(statistics.median(elapsed), 3) if elapsed else None,
        "case_elapsed_p95_ms": round(elapsed[math.ceil(len(elapsed) * 0.95) - 1], 3)
        if elapsed
        else None,
        "request_latency_p50_ms": round(statistics.median(request_latency), 3)
        if request_latency
        else None,
        "request_latency_p95_ms": round(
            request_latency[math.ceil(len(request_latency) * 0.95) - 1], 3
        )
        if request_latency
        else None,
    }


def run(
    args: argparse.Namespace, *, completion_call: CompletionCall = post_json_completion
) -> None:
    if args.output.exists() or args.private_dir.exists():
        raise FileExistsError("existing output requires manual audit; never overwrite")
    protocol, protocol_sha = load_protocol(args.protocol, args.model_path)
    cases = load_cases(INPUTS["dataset"])
    if tuple(case["id"] for case in cases) != CASE_ORDER:
        raise ValueError("case order differs")
    if (
        sum(event["occurrence"] != "nonoccurring" for case in cases for event in case["events"])
        != 19
    ):
        raise ValueError("actionable event denominator differs")
    v4.verify_container(args.container_name, args.model_path)
    if args.private_dir.resolve().is_relative_to(ROOT):
        raise ValueError("private raw output must stay outside repository")
    args.private_dir.mkdir(mode=0o700, parents=False)
    args.private_dir.chmod(0o700)
    if stat.S_IMODE(args.private_dir.stat().st_mode) != 0o700:
        raise ValueError("private output permissions differ")
    request = protocol["request_policy"]
    policy = RequestPolicy(
        max_tokens=request["max_tokens"],
        temperature=request["temperature"],
        repeat_penalty=request["repeat_penalty"],
        stop=tuple(request["stop"]),
        timeout_seconds=request["timeout_seconds"],
        seed=request["seed"],
    )
    rows = []
    with args.output.open("x", encoding="utf-8") as stream:
        v4._append(stream, {"event": "header", "protocol_sha256": protocol_sha})
        for case in cases:
            v4._append(stream, {"event": "begin", "case_id": case["id"]})
            row = call_case(case, policy, args.private_dir, completion_call=completion_call)
            v4._append(stream, row)
            rows.append(row)
        v4._append(stream, {"event": "summary", **summarize(rows, cases)})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--private-dir", required=True, type=Path)
    parser.add_argument("--container-name", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
