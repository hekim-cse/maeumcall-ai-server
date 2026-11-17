"""Run the frozen ES owner-oracle dual-query diagnostic locally.

Reviewed A, E, B and occurrence enter both prompts. Gold relation and route
are scoring-only. Interrupted outputs are retained for manual audit, never
resumed or overwritten.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import stat
import statistics
from collections import Counter
from pathlib import Path

from experiments.as_safety_dual_query_v1.contract import (
    ARMS,
    combine_decisions,
    decision_messages,
    decision_schema,
    validate_decision,
)
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.transport import RequestPolicy, post_json_completion
from experiments.as_safety_v4 import run as v4
from experiments.as_safety_v4.cases import load_cases
from experiments.as_safety_v4.contract import route_for_events

ROOT = v4.ROOT
KIND = "as_safety_dual_query_v1_development_v1"
SCOPE = "exposed_ai_authored_owner_oracle_dual_query_development_only"
IMAGE = v4.IMAGE
MODEL_SHA = v4.MODEL_SHA
RUNTIME = v4.RUNTIME
REQUEST = v4.REQUEST
RELATIONS = ("current", "other", "unknown")
CATEGORIES = ("observed_current", "uncertain_current", "observed_other")
CONTRAST_PAIRS = (("ES01", "ES09"), ("ES02", "ES11"))
ROUTE_POLICY = {
    "implementation": "experiments.as_safety_v4.contract.route_for_events",
    "observed_current": "safety_action_required",
    "uncertain_current": "confirming_safety_status",
    "observed_other": "collecting_service_request",
    "unknown_or_failed": "confirming_safety_status",
    "priority": [
        "safety_action_required",
        "confirming_safety_status",
        "collecting_service_request",
    ],
    "multi_event_example": "ES06: observed current takes priority over other or failed event",
}
INPUTS = {
    **v4.INPUTS,
    "dual_query_method": ROOT / "docs/portfolio/nlu_safety_dual_query_v1_method.md",
}
PROTOCOL_FIELDS = {
    "kind",
    "claim_scope",
    "case_order",
    "event_order",
    "arm_order",
    "frozen_code_commit",
    "input_hashes",
    "source_manifest",
    "model_sha256",
    "server_image_digest",
    "request_policy",
    "local_runtime",
    "retry_policy",
    "private_output",
    "route_policy",
}
REQUIRED_SOURCES = v4.REQUIRED_V4_SOURCES | {
    "experiments/as_safety_dual_query_v1/__init__.py",
    "experiments/as_safety_dual_query_v1/contract.py",
    "experiments/as_safety_dual_query_v1/run.py",
    "experiments/as_safety_dual_query_v1/verify.py",
}


def _source_paths(commit: str) -> set[str]:
    paths: set[str] = set()
    for prefix in (
        "experiments/as_safety_v2",
        "experiments/as_safety_v4",
        "experiments/as_safety_dual_query_v1",
    ):
        output = v4._git("ls-tree", "-r", "--name-only", commit, "--", prefix)
        paths.update(path for path in output.decode().splitlines() if path.endswith(".py"))
    return paths


def eligible_events(cases: list[dict]) -> list[tuple[str, int, dict, dict]]:
    """Only reviewed actionable events with a known owner; ES17 stays out."""
    if tuple(case["id"] for case in cases) != v4.CASE_ORDER:
        raise ValueError("ES case order differs")
    selected = []
    for case in cases:
        for index, gold in enumerate(case["events"], 1):
            if gold["occurrence"] == "nonoccurring" or gold["hazard_owner_span"] is None:
                continue
            selected.append((f"{case['id']}-{index}", index, case, gold))
    counts = Counter(
        f"{gold['occurrence']}_{gold['owner_to_target']}" for _, _, _, gold in selected
    )
    if (
        len(selected) != 18
        or len({case["id"] for _, _, case, _ in selected}) != 17
        or counts
        != {
            "observed_current": 8,
            "uncertain_current": 1,
            "observed_other": 9,
        }
    ):
        raise ValueError("reviewed event denominator differs")
    return selected


def event_order(cases: list[dict]) -> list[str]:
    return [key for key, _, _, _ in eligible_events(cases)]


def arm_order(cases: list[dict]) -> list[dict]:
    return [
        {"event_id": key, "arms": list(ARMS if ordinal % 2 == 0 else reversed(ARMS))}
        for ordinal, (key, _, _, _) in enumerate(eligible_events(cases))
    ]


def build_protocol(commit: str, cases: list[dict]) -> dict:
    if type(commit) is not str or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("full code commit required")
    sources = _source_paths(commit)
    if not REQUIRED_SOURCES <= sources:
        raise ValueError("required source absent from frozen commit")
    inputs = {}
    for key, path in INPUTS.items():
        relative = path.relative_to(ROOT).as_posix()
        frozen = v4._committed(commit, relative)
        if frozen != path.read_bytes():
            raise ValueError(f"input differs from commit: {key}")
        inputs[key] = v4.digest(frozen)
    manifest = {}
    for relative in sorted(sources):
        frozen = v4._committed(commit, relative)
        if frozen != (ROOT / relative).read_bytes():
            raise ValueError(f"source differs from commit: {relative}")
        manifest[relative] = v4.digest(frozen)
    return {
        "kind": KIND,
        "claim_scope": SCOPE,
        "case_order": list(dict.fromkeys(case["id"] for _, _, case, _ in eligible_events(cases))),
        "event_order": event_order(cases),
        "arm_order": arm_order(cases),
        "frozen_code_commit": commit,
        "input_hashes": inputs,
        "source_manifest": manifest,
        "model_sha256": MODEL_SHA,
        "server_image_digest": IMAGE,
        "request_policy": REQUEST,
        "local_runtime": RUNTIME,
        "retry_policy": "no_retry_manual_audit_on_interruption",
        "private_output": "outside_repository_mode_0700_files_0600",
        "route_policy": ROUTE_POLICY,
    }


def load_protocol(path: Path, model_path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    protocol = json.loads(raw)
    if type(protocol) is not dict or set(protocol) != PROTOCOL_FIELDS:
        raise ValueError("protocol fields differ")
    commit = protocol["frozen_code_commit"]
    if type(commit) is not str or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("frozen commit differs")
    cases = load_cases(INPUTS["dataset"])
    expected = build_protocol(commit, cases)
    if protocol != expected or v4.digest_file(model_path) != MODEL_SHA:
        raise ValueError("protocol or model differs from frozen identity")
    try:
        relative = path.resolve().relative_to(ROOT).as_posix()
    except ValueError as error:
        raise ValueError("protocol must be in repository") from error
    if v4._git("show", f"HEAD:{relative}") != raw:
        raise ValueError("protocol must be committed before model calls")
    if v4._git("status", "--porcelain").strip():
        raise ValueError("checkout differs before model calls")
    return protocol, v4.digest(raw)


def call_event(
    event_id: str,
    case: dict,
    gold: dict,
    arm: str,
    policy: RequestPolicy,
    private_dir: Path,
    *,
    completion_call: v4.CompletionCall = post_json_completion,
) -> dict:
    stage, raw = v4._call(
        messages=decision_messages(case, gold, arm),
        schema=decision_schema(),
        policy=policy,
        raw_path=private_dir / f"{event_id}-{arm}.json.txt",
        completion_call=completion_call,
    )
    stage["decision"] = None
    if stage["error_code"] is None and raw is not None:
        try:
            stage["decision"] = validate_decision(raw)
        except ValidationError as error:
            stage.update(status="contract_error", error_code=error.code, error_field=error.field)
        else:
            stage["status"] = "validated"
    return stage


def _relations(rows: list[dict], cases: list[dict]) -> tuple[dict[str, str], dict[str, bool]]:
    by_event = {(row["event_id"], row["arm"]): row["stage"] for row in rows}
    relations = {}
    failed = {}
    for key, _, _, _ in eligible_events(cases):
        current = by_event[(key, "current")]
        distinct = by_event[(key, "distinct")]
        has_error = current["status"] != "validated" or distinct["status"] != "validated"
        failed[key] = has_error
        relations[key] = (
            "unknown" if has_error else combine_decisions(current["decision"], distinct["decision"])
        )
    return relations, failed


def _routes(
    relations: dict[str, str], failed: dict[str, bool], cases: list[dict]
) -> dict[str, str]:
    routes = {}
    for case in cases:
        values = []
        case_failed = False
        present = False
        for index, gold in enumerate(case["events"], 1):
            key = f"{case['id']}-{index}"
            if key in relations:
                present = True
                values.append(relations[key])
                case_failed |= failed[key]
            elif gold["occurrence"] == "nonoccurring":
                values.append(None)
            elif gold["hazard_owner_span"] is None and gold["owner_to_target"] == "unknown":
                # ES17 is outside this owner-oracle diagnostic.
                break
            else:
                raise ValueError("unexpected excluded actionable event in route")
        if present:
            routes[case["id"]] = route_for_events(
                [{"occurrence": event["occurrence"]} for event in case["events"]],
                values,
                overflow=case["overflow"],
                failed=case_failed,
            )
    if len(routes) != 17:
        raise ValueError("route denominator differs")
    return routes


def summarize(rows: list[dict], cases: list[dict]) -> dict:
    selected = eligible_events(cases)
    by_event = {(row["event_id"], row["arm"]): row["stage"] for row in rows}
    if len(rows) != 36 or set(by_event) != {
        (key, arm) for key, _, _, _ in selected for arm in ARMS
    }:
        raise ValueError("event/arm result denominator differs")
    relations, failed = _relations(rows, cases)
    routes = _routes(relations, failed, cases)
    category_correct = dict.fromkeys(CATEGORIES, 0)
    output_distribution = {"current": 0, "other": 0, "unknown": 0}
    status = Counter()
    decisions = {arm: {"yes": 0, "no": 0, "unknown": 0} for arm in ARMS}
    abstention = Counter({"error_pair": 0, "any_unknown": 0, "contradiction": 0, "both_no": 0})
    directional = Counter(
        {
            "observed_current_to_other": 0,
            "observed_current_to_unknown": 0,
            "uncertain_current_to_other": 0,
            "uncertain_current_to_unknown": 0,
            "observed_other_to_current": 0,
            "observed_other_to_unknown": 0,
        }
    )
    correct = {}
    for key, _, _, gold in selected:
        category = f"{gold['occurrence']}_{gold['owner_to_target']}"
        good = not failed[key] and relations[key] == gold["owner_to_target"]
        correct[key] = good
        category_correct[category] += int(good)
        output_distribution[relations[key]] += 1
        if relations[key] != gold["owner_to_target"]:
            directional[f"{category}_to_{relations[key]}"] += 1
        current = by_event[(key, "current")]
        distinct = by_event[(key, "distinct")]
        if failed[key]:
            abstention["error_pair"] += 1
        elif "unknown" in (current["decision"], distinct["decision"]):
            abstention["any_unknown"] += 1
        elif current["decision"] == distinct["decision"] == "yes":
            abstention["contradiction"] += 1
        elif current["decision"] == distinct["decision"] == "no":
            abstention["both_no"] += 1
        for arm in ARMS:
            stage = by_event[(key, arm)]
            status[stage["status"]] += 1
            if stage["status"] == "validated":
                decisions[arm][stage["decision"]] += 1
    case_map = {case["id"]: case for case in cases}
    pair_detail = {
        f"{first}/{second}": all(
            routes[case_id] == case_map[case_id]["expected_route"]
            and all(correct[key] for key, _, case, _ in selected if case["id"] == case_id)
            for case_id in (first, second)
        )
        for first, second in CONTRAST_PAIRS
    }
    latencies = sorted(
        sum(by_event[(key, arm)]["request_latency_ms"] for arm in ARMS) for key, _, _, _ in selected
    )
    question_latencies = {
        arm: sorted(by_event[(key, arm)]["request_latency_ms"] for key, _, _, _ in selected)
        for arm in ARMS
    }
    case_latencies = sorted(
        sum(
            by_event[(key, arm)]["request_latency_ms"]
            for key, _, item, _ in selected
            if item["id"] == case_id
            for arm in ARMS
        )
        for case_id in routes
    )
    decided = output_distribution["current"] + output_distribution["other"]
    decided_correct = sum(correct[key] and relations[key] != "unknown" for key in correct)
    route_correct = sum(
        routes[case_id] == case_map[case_id]["expected_route"] for case_id in routes
    )
    return {
        "cases": 17,
        "events": 18,
        "requests": 36,
        "claim_scope": SCOPE,
        "relation_correct": sum(correct.values()),
        "category_denominators": {
            "observed_current": 8,
            "uncertain_current": 1,
            "observed_other": 9,
        },
        "category_correct": category_correct,
        "status_counts": dict(sorted(status.items())),
        "decision_distribution": decisions,
        "output_distribution": output_distribution,
        "abstention_reasons": dict(abstention),
        "directional_relation_errors": dict(directional),
        "contract_errors": status["contract_error"],
        "response_errors": status["response_error"],
        "unresolved_pairs": output_distribution["unknown"],
        "decided_relation_count": decided,
        "decided_relation_correct": decided_correct,
        "relation_decision_denominator": 18,
        "relation_decision_rate": round(decided / 18, 6),
        "decided_relation_accuracy_denominator": decided,
        "decided_relation_accuracy": round(decided_correct / decided, 6) if decided else None,
        "route_correct": route_correct,
        "route_predictions": routes,
        "es06_route": routes["ES06"],
        "contrast_pairs_correct": sum(pair_detail.values()),
        "contrast_pairs": pair_detail,
        "missed_direct_current": sum(
            case_map[key]["expected_route"] == "safety_action_required"
            and value != "safety_action_required"
            for key, value in routes.items()
        ),
        "false_direct_other": sum(
            case_map[key]["expected_route"] == "collecting_service_request"
            and value == "safety_action_required"
            for key, value in routes.items()
        ),
        "event_request_latency_count": 18,
        "event_request_latency_p50_ms": round(statistics.median(latencies), 3),
        "event_request_latency_p95_ms": round(latencies[math.ceil(len(latencies) * 0.95) - 1], 3),
        "question_request_latency_ms": {
            arm: {
                "count": 18,
                "p50": round(statistics.median(values), 3),
                "p95": round(values[math.ceil(len(values) * 0.95) - 1], 3),
            }
            for arm, values in question_latencies.items()
        },
        "case_request_latency_count": 17,
        "case_request_latency_p50_ms": round(statistics.median(case_latencies), 3),
        "case_request_latency_p95_ms": round(
            case_latencies[math.ceil(len(case_latencies) * 0.95) - 1], 3
        ),
        "gate_met": (
            category_correct == {"observed_current": 8, "uncertain_current": 1, "observed_other": 9}
            and route_correct == 17
            and sum(pair_detail.values()) == 2
            and status["contract_error"] == status["response_error"] == 0
        ),
    }


def run(
    args: argparse.Namespace, *, completion_call: v4.CompletionCall = post_json_completion
) -> None:
    if args.output.exists() or args.private_dir.exists():
        raise FileExistsError("existing output requires manual audit; never overwrite")
    protocol, protocol_sha = load_protocol(args.protocol, args.model_path)
    cases = load_cases(INPUTS["dataset"])
    selected = eligible_events(cases)
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
    lookup = {key: (case, gold) for key, _, case, gold in selected}
    rows = []
    with args.output.open("x", encoding="utf-8") as stream:
        v4._append(stream, {"event": "header", "protocol_sha256": protocol_sha})
        for assignment in protocol["arm_order"]:
            key = assignment["event_id"]
            case, gold = lookup[key]
            for arm in assignment["arms"]:
                v4._append(stream, {"event": "begin", "event_id": key, "arm": arm})
                stage = call_event(
                    key, case, gold, arm, policy, args.private_dir, completion_call=completion_call
                )
                row = {"event": "end", "event_id": key, "arm": arm, "stage": stage}
                v4._append(stream, row)
                rows.append(row)
        v4._append(stream, {"event": "summary", **summarize(rows, cases)})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build-protocol")
    build.add_argument("--output", required=True, type=Path)
    execute = sub.add_parser("run")
    execute.add_argument("--protocol", required=True, type=Path)
    execute.add_argument("--model-path", required=True, type=Path)
    execute.add_argument("--output", required=True, type=Path)
    execute.add_argument("--private-dir", required=True, type=Path)
    execute.add_argument("--container-name", required=True)
    args = parser.parse_args()
    if args.command == "build-protocol":
        if v4._git("status", "--porcelain").strip():
            raise ValueError("checkout must be clean before protocol build")
        commit = v4._git("rev-parse", "HEAD").decode().strip()
        protocol = build_protocol(commit, load_cases(INPUTS["dataset"]))
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(protocol, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
    else:
        run(args)


if __name__ == "__main__":
    main()
