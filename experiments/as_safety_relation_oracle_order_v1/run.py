"""Run the frozen ES owner-oracle relation-order diagnostic locally.

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

from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.transport import RequestPolicy, post_json_completion
from experiments.as_safety_v4 import run as v4
from experiments.as_safety_v4.cases import load_cases
from experiments.as_safety_v4.contract import route_for_events

ROOT = v4.ROOT
KIND = "as_safety_relation_oracle_order_v1_development_v1"
SCOPE = "exposed_ai_authored_owner_oracle_relation_order_development_only"
IMAGE = v4.IMAGE
MODEL_SHA = v4.MODEL_SHA
RUNTIME = v4.RUNTIME
REQUEST = v4.REQUEST
ARMS = ("forward", "reverse")
RELATIONS = ("current", "other", "unknown")
CATEGORIES = ("observed_current", "uncertain_current", "observed_other")
CONTRAST_PAIRS = (("ES01", "ES09"), ("ES02", "ES11"))
ROUTE_POLICY = {
    "implementation": "experiments.as_safety_v4.contract.route_for_events",
    "observed_current": "safety_action_required",
    "uncertain_current": "confirming_safety_status",
    "observed_other": "collecting_service_request",
    "unknown_or_failed": "confirming_safety_status",
    "priority": ["safety_action_required", "confirming_safety_status", "collecting_service_request"],
    "multi_event_example": "ES06: observed current takes priority over other or failed event",
}
INPUTS = {
    **v4.INPUTS,
    "relation_method": ROOT / "docs/portfolio/nlu_safety_relation_oracle_order_v1_method.md",
}
PROTOCOL_FIELDS = {
    "kind", "claim_scope", "case_order", "event_order", "arm_order",
    "frozen_code_commit", "input_hashes", "source_manifest", "model_sha256",
    "server_image_digest", "request_policy", "local_runtime", "retry_policy",
    "private_output", "route_policy",
}
REQUIRED_SOURCES = v4.REQUIRED_V4_SOURCES | {
    "experiments/as_safety_relation_oracle_order_v1/__init__.py",
    "experiments/as_safety_relation_oracle_order_v1/run.py",
    "experiments/as_safety_relation_oracle_order_v1/verify.py",
}


def _source_paths(commit: str) -> set[str]:
    paths: set[str] = set()
    for prefix in (
        "experiments/as_safety_v2", "experiments/as_safety_v4",
        "experiments/as_safety_relation_oracle_order_v1",
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
    counts = Counter(f"{gold['occurrence']}_{gold['owner_to_target']}" for _, _, _, gold in selected)
    if len(selected) != 18 or len({case["id"] for _, _, case, _ in selected}) != 17 or counts != {
        "observed_current": 8, "uncertain_current": 1, "observed_other": 9,
    }:
        raise ValueError("reviewed event denominator differs")
    return selected


def event_order(cases: list[dict]) -> list[str]:
    return [key for key, _, _, _ in eligible_events(cases)]


def arm_order(cases: list[dict]) -> list[dict]:
    return [
        {"event_id": key, "arms": list(ARMS if ordinal % 2 == 0 else reversed(ARMS))}
        for ordinal, (key, _, _, _) in enumerate(eligible_events(cases))
    ]


def relation_schema() -> dict:
    return {
        "type": "object", "properties": {"relation": {"type": "string", "enum": list(RELATIONS)}},
        "required": ["relation"], "additionalProperties": False,
    }


DEFINITIONS = {
    "current": "current: 위험 사건의 주체가 접수 대상 제품 자체이거나 그 제품에 속한 부품이다.",
    "other": "other: 위험 사건의 주체가 접수 대상 제품과 별개의 제품이나 물건이다.",
    "unknown": "unknown: 주어진 근거만으로 주체와 접수 대상의 관계를 판정할 수 없다.",
}


def relation_messages(case: dict, gold: dict, arm: str) -> list[dict[str, str]]:
    if arm not in ARMS or gold["hazard_owner_span"] is None:
        raise ValueError("invalid owner-oracle request")
    definitions = list(DEFINITIONS if arm == "forward" else reversed(DEFINITIONS))
    system = (
        "A/S 위험 사건의 주체와 접수 대상 제품의 관계를 판정하세요. "
        "아래 정의 중 하나만 선택하고 relation 단일 필드 JSON 객체만 답하세요.\n"
        + "\n".join(DEFINITIONS[key] for key in definitions)
    )
    user = {
        "user_message": case["user_message"],
        "target": case["target"],
        "event_span": gold["event_span"],
        "hazard_owner_span": gold["hazard_owner_span"],
        "occurrence": gold["occurrence"],
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False, sort_keys=True)},
    ]


def validate_relation(raw: str) -> str:
    item = parse_model_json(raw)
    if type(item) is not dict or set(item) != {"relation"}:
        raise ValidationError("relation_fields_invalid", "relation")
    if type(item["relation"]) is not str or item["relation"] not in RELATIONS:
        raise ValidationError("relation_enum_invalid", "relation")
    return item["relation"]


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
        "kind": KIND, "claim_scope": SCOPE,
        "case_order": list(dict.fromkeys(case["id"] for _, _, case, _ in eligible_events(cases))),
        "event_order": event_order(cases), "arm_order": arm_order(cases),
        "frozen_code_commit": commit, "input_hashes": inputs, "source_manifest": manifest,
        "model_sha256": MODEL_SHA, "server_image_digest": IMAGE,
        "request_policy": REQUEST, "local_runtime": RUNTIME,
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
    event_id: str, case: dict, gold: dict, arm: str, policy: RequestPolicy,
    private_dir: Path, *, completion_call: v4.CompletionCall = post_json_completion,
) -> dict:
    stage, raw = v4._call(
        messages=relation_messages(case, gold, arm), schema=relation_schema(),
        policy=policy, raw_path=private_dir / f"{event_id}-{arm}.json.txt",
        completion_call=completion_call,
    )
    stage["relation"] = None
    if stage["error_code"] is None and raw is not None:
        try:
            stage["relation"] = validate_relation(raw)
        except ValidationError as error:
            stage.update(status="contract_error", error_code=error.code, error_field=error.field)
        else:
            stage["status"] = "validated"
    return stage


def _routes(rows: list[dict], cases: list[dict], arm: str) -> dict[str, str]:
    by_event = {(row["event_id"], row["arm"]): row["stage"] for row in rows}
    result = {}
    for case in cases:
        if not any((f"{case['id']}-{i}", arm) in by_event for i in range(1, len(case["events"]) + 1)):
            continue
        relations = []
        failed = False
        for index, gold in enumerate(case["events"], 1):
            stage = by_event.get((f"{case['id']}-{index}", arm))
            if stage is None:
                if gold["occurrence"] != "nonoccurring":
                    raise ValueError("unexpected excluded actionable event in route")
                relations.append(None)
            else:
                relations.append(stage["relation"])
                failed |= stage["status"] != "validated"
        result[case["id"]] = route_for_events(
            [{"occurrence": event["occurrence"]} for event in case["events"]],
            relations, overflow=case["overflow"], failed=failed,
        )
    return result


def summarize(rows: list[dict], cases: list[dict]) -> dict:
    selected = eligible_events(cases)
    by_event = {(row["event_id"], row["arm"]): row["stage"] for row in rows}
    if len(rows) != 36 or set(by_event) != {(key, arm) for key, _, _, _ in selected for arm in ARMS}:
        raise ValueError("event/arm result denominator differs")
    result = {"cases": 17, "events": 18, "requests": 36, "claim_scope": SCOPE, "arms": {}}
    correct_by_arm: dict[str, dict[str, bool]] = {}
    routes_by_arm: dict[str, dict[str, str]] = {}
    for arm in ARMS:
        category_correct = dict.fromkeys(CATEGORIES, 0)
        outputs = dict.fromkeys(RELATIONS, 0)
        status = Counter()
        correct = {}
        for key, _, _, gold in selected:
            stage = by_event[(key, arm)]
            category = f"{gold['occurrence']}_{gold['owner_to_target']}"
            good = stage["status"] == "validated" and stage["relation"] == gold["owner_to_target"]
            correct[key] = good
            category_correct[category] += good
            status[stage["status"]] += 1
            if stage["status"] == "validated":
                outputs[stage["relation"]] += 1
        routes = _routes(rows, cases, arm)
        case_map = {case["id"]: case for case in cases}
        pair_detail = {
            f"{first}/{second}": all(
                routes[case_id] == case_map[case_id]["expected_route"]
                and all(correct[key] for key, _, case, _ in selected if case["id"] == case_id)
                for case_id in (first, second)
            ) for first, second in CONTRAST_PAIRS
        }
        latencies = sorted(by_event[(key, arm)]["request_latency_ms"] for key, _, _, _ in selected)
        result["arms"][arm] = {
            "relation_correct": sum(correct.values()),
            "category_denominators": {"observed_current": 8, "uncertain_current": 1, "observed_other": 9},
            "category_correct": category_correct,
            "status_counts": dict(sorted(status.items())), "output_distribution": outputs,
            "contract_errors": status["contract_error"],
            "response_errors": status["response_error"],
            "route_correct": sum(routes[case_id] == case_map[case_id]["expected_route"] for case_id in routes),
            "route_predictions": routes,
            "es06_route": routes["ES06"],
            "contrast_pairs_correct": sum(pair_detail.values()), "contrast_pairs": pair_detail,
            "missed_direct_current": sum(case_map[key]["expected_route"] == "safety_action_required" and value != "safety_action_required" for key, value in routes.items()),
            "false_direct_other": sum(case_map[key]["expected_route"] == "collecting_service_request" and value == "safety_action_required" for key, value in routes.items()),
            "request_latency_p50_ms": round(statistics.median(latencies), 3),
            "request_latency_p95_ms": round(latencies[math.ceil(len(latencies) * .95) - 1], 3),
        }
        correct_by_arm[arm] = correct
        routes_by_arm[arm] = routes
    forward, reverse = correct_by_arm["forward"], correct_by_arm["reverse"]
    result["paired"] = {
        "both_correct": sum(forward[key] and reverse[key] for key in forward),
        "both_wrong": sum(not forward[key] and not reverse[key] for key in forward),
        "forward_correct_reverse_wrong": sum(forward[key] and not reverse[key] for key in forward),
        "forward_wrong_reverse_correct": sum(not forward[key] and reverse[key] for key in forward),
        "arm_prediction_agreement": sum(
            by_event[(key, "forward")]["relation"] == by_event[(key, "reverse")]["relation"]
            and by_event[(key, "forward")]["status"] == "validated"
            and by_event[(key, "reverse")]["status"] == "validated"
            for key in forward
        ),
    }
    result["gate_met"] = (
        all(
            result["arms"][arm]["category_correct"]
            == result["arms"][arm]["category_denominators"]
            and result["arms"][arm]["route_correct"] == 17
            and result["arms"][arm]["contrast_pairs_correct"] == 2
            and result["arms"][arm]["contract_errors"] == 0
            and result["arms"][arm]["response_errors"] == 0
            for arm in ARMS
        )
        and result["paired"]["arm_prediction_agreement"] == 18
    )
    return result


def run(args: argparse.Namespace, *, completion_call: v4.CompletionCall = post_json_completion) -> None:
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
        max_tokens=request["max_tokens"], temperature=request["temperature"],
        repeat_penalty=request["repeat_penalty"], stop=tuple(request["stop"]),
        timeout_seconds=request["timeout_seconds"], seed=request["seed"],
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
                stage = call_event(key, case, gold, arm, policy, args.private_dir, completion_call=completion_call)
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
