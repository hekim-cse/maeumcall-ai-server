"""Run frozen R relation-only and O owner-oracle Stage2 ES diagnostics."""

from __future__ import annotations

import argparse
import json
import math
import re
import stat
import statistics
import time
from pathlib import Path

from experiments.as_safety_oracle_event_v1 import verify as baseline_verify
from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.transport import RequestPolicy, post_json_completion
from experiments.as_safety_v4 import run as v4
from experiments.as_safety_v4.cases import load_cases
from experiments.as_safety_v4.contract import (
    _STAGE2_INSTRUCTION,
    route_for_events,
    stage2_messages,
    stage2_schema,
    validate_stage2,
)

ROOT = v4.ROOT
KIND = "as_safety_stage2_ablation_v1_development_v1"
SCOPE = "already_exposed_ai_authored_stage2_ablation_development_only"
CASE_ORDER = v4.CASE_ORDER
IMAGE = v4.IMAGE
MODEL_SHA = v4.MODEL_SHA
RUNTIME = v4.RUNTIME
REQUEST = v4.REQUEST
INPUTS = {
    "dataset": v4.INPUTS["dataset"],
    "review": v4.INPUTS["review"],
    "field_review": v4.INPUTS["field_review"],
    "method": ROOT / "docs/portfolio/nlu_safety_stage2_ablation_v1_method.md",
    "baseline_protocol": v4.DATA / "as-safety-oracle-event-v1-development-protocol.v1.json",
    "baseline_journal": v4.DATA / "as-safety-oracle-event-v1-development-journal.v1.jsonl",
    "baseline_verification": v4.DATA / "as-safety-oracle-event-v1-development-verification.v1.json",
}
PROTOCOL_FIELDS = v4.PROTOCOL_FIELDS
REQUIRED_SOURCES = v4.REQUIRED_V4_SOURCES | {
    "experiments/as_safety_oracle_event_v1/__init__.py",
    "experiments/as_safety_oracle_event_v1/run.py",
    "experiments/as_safety_oracle_event_v1/verify.py",
    "experiments/as_safety_stage2_ablation_v1/__init__.py",
    "experiments/as_safety_stage2_ablation_v1/run.py",
    "experiments/as_safety_stage2_ablation_v1/verify.py",
}
CompletionCall = v4.CompletionCall
ARMS = ("R", "O")
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
        "experiments/as_safety_stage2_ablation_v1",
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
    if v4._git("status", "--porcelain").strip():
        raise ValueError("checkout differs before model calls")
    return protocol, v4.digest(raw)


R_INSTRUCTION = (
    _STAGE2_INSTRUCTION.replace(
        "해당 사건의 발생 물건 또는 그 부위·위치를 짧은 원문 구절로 인용하세요. ",
        "",
    )
    .replace(
        "current 또는 other라면 hazard_owner_span을 반드시 인용하세요. ",
        "",
    )
    .replace(
        "JSON 객체에 hazard_owner_span과 owner_to_target만 넣으세요.",
        "JSON 객체에 owner_to_target만 넣으세요.",
    )
)
O_INSTRUCTION = _STAGE2_INSTRUCTION.replace(
    "이전 단계의 주체·소속 추측이나 검수 정답은 주어지지 않습니다. ",
    "위험 주체 B의 검수 구절만 주어졌으며 관계·최종 경로 정답은 주어지지 않습니다. ",
)
if (
    O_INSTRUCTION == _STAGE2_INSTRUCTION
    or "hazard_owner_span" in R_INSTRUCTION
    or "앞 문장의 물건을 가리키는 경우에는 그 연결을 고려하세요." not in R_INSTRUCTION
):
    raise RuntimeError("Stage2 instruction insertion point changed")


def relation_only_schema() -> dict:
    return {
        "type": "object",
        "properties": {"owner_to_target": {"enum": ["current", "other", "unknown"]}},
        "required": ["owner_to_target"],
        "additionalProperties": False,
    }


def relation_only_decision(raw: str) -> str:
    parsed = parse_model_json(raw)
    if type(parsed) is not dict or set(parsed) != {"owner_to_target"}:
        raise ValidationError("fields_invalid", "stage2")
    relation = parsed["owner_to_target"]
    if type(relation) is not str or relation not in {"current", "other", "unknown"}:
        raise ValidationError("relation_invalid", "owner_to_target")
    return relation


def ablation_messages(
    arm: str, message: str, event: dict, args: dict, *, gold_owner: dict | None
) -> list[dict[str, str]]:
    if arm not in ARMS:
        raise ValueError("arm differs")
    messages = stage2_messages(message, event, **args)
    content = messages[1]["content"]
    if not content.endswith(_STAGE2_INSTRUCTION):
        raise ValueError("Stage2 instruction boundary changed")
    if arm == "R":
        if gold_owner is not None:
            raise ValueError("R must not receive gold owner")
        messages[1]["content"] = content[: -len(_STAGE2_INSTRUCTION)] + R_INSTRUCTION
    else:
        if gold_owner is None:
            raise ValueError("O requires reviewed owner")
        hint = f"검수된 위험 주체 B: {gold_owner['clause_index']}. {gold_owner['quote']}\n"
        messages[1]["content"] = content[: -len(_STAGE2_INSTRUCTION)] + hint + O_INSTRUCTION
    return messages


def call_case(
    arm: str,
    case: dict,
    policy: RequestPolicy,
    private_dir: Path,
    *,
    completion_call: CompletionCall = post_json_completion,
) -> dict:
    """Call each eligible reviewed event once; score gold only after calls."""
    if arm not in ARMS:
        raise ValueError("arm differs")
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
        skip_reason = None
        if event["occurrence"] == "nonoccurring":
            skip_reason = "nonoccurring"
        elif arm == "O" and gold["hazard_owner_span"] is None:
            skip_reason = "owner_oracle_unavailable"
        if skip_reason:
            stage = v4._blank(called=False, skip_reason=skip_reason)
            stages.append({**stage, **public})
            relations.append(None)
            failed |= skip_reason == "owner_oracle_unavailable"
            continue
        gold_owner = (
            anchor_span(gold["hazard_owner_span"], clauses, field="hazard_owner_span")
            if arm == "O"
            else None
        )
        stage, raw = v4._call(
            messages=ablation_messages(arm, message, event, args, gold_owner=gold_owner),
            schema=relation_only_schema() if arm == "R" else stage2_schema(message),
            policy=policy,
            raw_path=private_dir / f"{arm}-{case['id']}-stage2-{index}.json.txt",
            completion_call=completion_call,
        )
        stage.update(public)
        if stage["error_code"] is None and raw is not None:
            try:
                if arm == "R":
                    decision = {
                        "owner_to_target": relation_only_decision(raw),
                        "hazard_owner_span": None,
                    }
                else:
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
        "arm": arm,
        "case_id": case["id"],
        "stage2": stages,
        "route": route,
        "request_count": sum(int(stage["called"]) for stage in stages),
        "model_call_latency_sum_ms": round(
            sum(stage["request_latency_ms"] or 0 for stage in stages), 3
        ),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def _percentiles(values: list[float]) -> tuple[float | None, float | None]:
    ordered = sorted(values)
    return (
        round(statistics.median(ordered), 3) if ordered else None,
        round(ordered[math.ceil(len(ordered) * 0.95) - 1], 3) if ordered else None,
    )


def eligible(arm: str, gold: dict) -> bool:
    return gold["occurrence"] != "nonoccurring" and (
        arm == "R" or gold["hazard_owner_span"] is not None
    )


def summarize_arm(arm: str, rows: list[dict], cases: list[dict]) -> dict:
    if (
        arm not in ARMS
        or len(rows) != len(cases)
        or tuple(row["case_id"] for row in rows) != tuple(case["id"] for case in cases)
        or any(row["arm"] != arm for row in rows)
    ):
        raise ValueError("arm, case count or order differs")
    category_counts = dict.fromkeys(RELATION_CATEGORIES, 0)
    category_relation_correct = dict.fromkeys(RELATION_CATEGORIES, 0)
    case_relation_correct: dict[str, bool] = {}
    for row, case in zip(rows, cases, strict=True):
        all_correct = True
        for stage, gold in zip(row["stage2"], case["events"], strict=True):
            if not eligible(arm, gold):
                continue
            category = f"{gold['occurrence']}_{gold['owner_to_target']}"
            if category not in category_counts:
                raise ValueError("gold relation category differs")
            category_counts[category] += 1
            correct = (
                stage["status"] == "validated"
                and stage["owner_to_target"] == gold["owner_to_target"]
            )
            category_relation_correct[category] += int(correct)
            all_correct &= correct
        case_relation_correct[case["id"]] = all_correct
    case_route_correct = {
        case["id"]: row["route"] == case["expected_route"]
        for row, case in zip(rows, cases, strict=True)
    }
    pairs = [pair for pair in CONTRAST_PAIRS if all(cid in case_route_correct for cid in pair)]
    case_p50, case_p95 = _percentiles([row["elapsed_ms"] for row in rows])
    request_p50, request_p95 = _percentiles(
        [stage["request_latency_ms"] for row in rows for stage in row["stage2"] if stage["called"]]
    )
    normal = "collecting_service_request"

    def observed_other(case: dict) -> bool:
        return case["expected_route"] == normal and any(
            gold["occurrence"] == "observed" and gold["owner_to_target"] == "other"
            for gold in case["events"]
        )

    return {
        "cases": len(rows),
        "gold_event_count": sum(len(case["events"]) for case in cases),
        "eligible_gold_event_count": sum(
            eligible(arm, gold) for case in cases for gold in case["events"]
        ),
        "skip_nonoccurring": sum(
            gold["occurrence"] == "nonoccurring" for case in cases for gold in case["events"]
        ),
        "skip_owner_unavailable": sum(
            arm == "O"
            and gold["occurrence"] != "nonoccurring"
            and gold["hazard_owner_span"] is None
            for case in cases
            for gold in case["events"]
        ),
        "relation_correct": sum(category_relation_correct.values()),
        "category_counts": category_counts,
        "category_relation_correct": category_relation_correct,
        "route_correct_all": sum(case_route_correct.values()),
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
        "contrast_pair_count": len(pairs),
        "contrast_pairs_correct": sum(
            all(case_relation_correct[cid] and case_route_correct[cid] for cid in pair)
            for pair in pairs
        ),
        "other_observed_cases": sum(observed_other(case) for case in cases),
        "false_direct_other": sum(
            observed_other(case) and row["route"] == "safety_action_required"
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
        "case_elapsed_p50_ms": case_p50,
        "case_elapsed_p95_ms": case_p95,
        "request_latency_p50_ms": request_p50,
        "request_latency_p95_ms": request_p95,
    }


def baseline_paired_summary(journal_path: Path, cases: list[dict]) -> dict:
    rows = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()]
    ends = {row["case_id"]: row for row in rows if row.get("event") == "end"}
    if set(ends) != {case["id"] for case in cases}:
        raise ValueError("baseline case inventory differs")
    all_correct = owner_correct = 0
    route_all = route_owner = model_owner = 0
    for case in cases:
        row = ends[case["id"]]
        if row["request_count"]:
            route_all += row["route"] == case["expected_route"]
            if all(
                gold["hazard_owner_span"] is not None
                for gold in case["events"]
                if gold["occurrence"] != "nonoccurring"
            ):
                model_owner += 1
                route_owner += row["route"] == case["expected_route"]
        for stage, gold in zip(row["stage2"], case["events"], strict=True):
            if gold["occurrence"] == "nonoccurring":
                continue
            correct = (
                stage["status"] == "validated"
                and stage["owner_to_target"] == gold["owner_to_target"]
            )
            all_correct += int(correct)
            if gold["hazard_owner_span"] is not None:
                owner_correct += int(correct)
    return {
        "relation_correct_all": all_correct,
        "relation_correct_owner_available": owner_correct,
        "model_involved_route_correct_all": route_all,
        "model_involved_route_correct_owner_available": route_owner,
        "owner_available_event_count": sum(
            gold["occurrence"] != "nonoccurring" and gold["hazard_owner_span"] is not None
            for case in cases
            for gold in case["events"]
        ),
        "owner_available_model_involved_cases": model_owner,
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
        sum(eligible("R", event) for case in cases for event in case["events"]) != 19
        or sum(eligible("O", event) for case in cases for event in case["events"]) != 18
    ):
        raise ValueError("eligible event denominator differs")
    prior = baseline_verify.verify(
        INPUTS["baseline_protocol"],
        INPUTS["baseline_journal"],
        args.baseline_private_dir,
        model_path=args.model_path,
    )
    if prior != json.loads(INPUTS["baseline_verification"].read_text(encoding="utf-8")):
        raise ValueError("baseline independent replay differs")
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
    rows_by_arm: dict[str, list[dict]] = {}
    with args.output.open("x", encoding="utf-8") as stream:
        v4._append(stream, {"event": "header", "protocol_sha256": protocol_sha})
        for arm in ARMS:
            arm_rows = []
            for case in cases:
                v4._append(stream, {"event": "begin", "arm": arm, "case_id": case["id"]})
                row = call_case(
                    arm, case, policy, args.private_dir, completion_call=completion_call
                )
                v4._append(stream, row)
                arm_rows.append(row)
            rows_by_arm[arm] = arm_rows
        v4._append(
            stream,
            {
                "event": "summary",
                "arms": {arm: summarize_arm(arm, rows_by_arm[arm], cases) for arm in ARMS},
                "baseline_paired": baseline_paired_summary(INPUTS["baseline_journal"], cases),
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--private-dir", required=True, type=Path)
    parser.add_argument("--baseline-private-dir", required=True, type=Path)
    parser.add_argument("--container-name", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
