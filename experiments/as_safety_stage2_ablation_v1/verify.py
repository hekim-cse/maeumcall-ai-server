"""Independently replay both frozen ES Stage2 ablation arms from private raw data."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

from experiments.as_safety_oracle_event_v1 import verify as prior
from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v4.cases import load_cases

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
DATASET = DATA / "as-safety-event-source-v4-exploration-reviewed.v1.json"
BASELINE_PROTOCOL = DATA / "as-safety-oracle-event-v1-development-protocol.v1.json"
BASELINE_JOURNAL = DATA / "as-safety-oracle-event-v1-development-journal.v1.jsonl"
BASELINE_VERIFICATION = DATA / "as-safety-oracle-event-v1-development-verification.v1.json"
INPUTS = {
    "dataset": DATASET,
    "review": ROOT / "docs/portfolio/nlu_safety_event_source_v4_review.md",
    "field_review": ROOT / "docs/portfolio/nlu_safety_event_source_v4_field_review.md",
    "method": ROOT / "docs/portfolio/nlu_safety_stage2_ablation_v1_method.md",
    "baseline_protocol": BASELINE_PROTOCOL,
    "baseline_journal": BASELINE_JOURNAL,
    "baseline_verification": BASELINE_VERIFICATION,
}
KIND = "as_safety_stage2_ablation_v1_development_v1"
SCOPE = "already_exposed_ai_authored_stage2_ablation_development_only"
CASE_ORDER = tuple(f"ES{i:02}" for i in range(1, 21))
ARMS = ("R", "O")
IMAGE = prior.IMAGE
MODEL_SHA = prior.MODEL_SHA
RUNTIME = prior.RUNTIME
POLICY = prior.POLICY
PROTOCOL_KEYS = prior.PROTOCOL_KEYS
BASE_KEYS = prior.BASE_KEYS
STAGE_KEYS = prior.STAGE2_KEYS
END_KEYS = prior.END_KEYS | {"arm"}
CATEGORIES = (
    "observed_current",
    "observed_other",
    "observed_unknown",
    "uncertain_current",
)
CONTRAST_PAIRS = (("ES01", "ES09"), ("ES02", "ES11"))
NORMAL = "collecting_service_request"


def _sources(commit: str) -> set[str]:
    paths = set()
    for prefix in (
        "experiments/as_safety_v2",
        "experiments/as_safety_v4",
        "experiments/as_safety_oracle_event_v1",
        "experiments/as_safety_stage2_ablation_v1",
    ):
        names = prior._git("ls-tree", "-r", "--name-only", commit, "--", prefix)
        paths.update(name for name in names.decode().splitlines() if name.endswith(".py"))
    required = {
        "experiments/as_safety_stage2_ablation_v1/__init__.py",
        "experiments/as_safety_stage2_ablation_v1/run.py",
        "experiments/as_safety_stage2_ablation_v1/verify.py",
    }
    if not required <= paths:
        raise ValueError("frozen ablation source package incomplete")
    return paths


def check_protocol(path: Path, model_path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    protocol = parse_model_json(raw.decode("utf-8"))
    if type(protocol) is not dict or set(protocol) != PROTOCOL_KEYS:
        raise ValueError("protocol fields differ")
    commit = protocol["frozen_code_commit"]
    if (
        type(commit) is not str
        or not prior.COMMIT_RE.fullmatch(commit)
        or protocol["kind"] != KIND
        or protocol["claim_scope"] != SCOPE
        or protocol["case_order"] != list(CASE_ORDER)
        or protocol["server_image_digest"] != IMAGE
        or protocol["model_sha256"] != MODEL_SHA
        or protocol["request_policy"] != POLICY
        or protocol["local_runtime"] != RUNTIME
        or protocol["retry_policy"] != "no_retry_manual_audit_on_interruption"
        or protocol["private_output"] != "outside_repository_mode_0700_files_0600"
    ):
        raise ValueError("protocol identity differs")
    if prior._digest_file(model_path) != MODEL_SHA:
        raise ValueError("model digest differs")
    manifest = protocol["source_manifest"]
    if type(manifest) is not dict or set(manifest) != _sources(commit):
        raise ValueError("source manifest paths differ")
    for relative, expected in manifest.items():
        frozen = prior._frozen(commit, relative)
        if (
            type(expected) is not str
            or not prior.SHA_RE.fullmatch(expected)
            or prior._digest(frozen) != expected
            or (ROOT / relative).read_bytes() != frozen
        ):
            raise ValueError(f"source manifest differs: {relative}")
    hashes = protocol["input_hashes"]
    if type(hashes) is not dict or set(hashes) != set(INPUTS):
        raise ValueError("input manifest paths differ")
    for key, source in INPUTS.items():
        frozen = prior._frozen(commit, source.relative_to(ROOT).as_posix())
        expected = hashes[key]
        if (
            type(expected) is not str
            or not prior.SHA_RE.fullmatch(expected)
            or prior._digest(frozen) != expected
            or source.read_bytes() != frozen
        ):
            raise ValueError(f"input manifest differs: {key}")
    try:
        relative = path.resolve().relative_to(ROOT).as_posix()
    except ValueError as error:
        raise ValueError("protocol must be inside repository") from error
    if prior._git("show", f"HEAD:{relative}") != raw:
        raise ValueError("protocol must be committed")
    return protocol, prior._digest(raw)


def _relation_only(raw: str) -> str:
    data = parse_model_json(raw)
    if type(data) is not dict or set(data) != {"owner_to_target"}:
        raise ValidationError("fields_invalid", "stage2")
    relation = data["owner_to_target"]
    if type(relation) is not str or relation not in prior.RELATIONS:
        raise ValidationError("relation_invalid", "owner_to_target")
    return relation


def _replay(stage: dict, raw: str | None, *, arm: str, message: str) -> dict | None:
    if stage["finish_reason"] is None:
        if (
            raw is not None
            or stage["status"] != "response_error"
            or stage["error_code"] not in prior.TRANSPORT_ERRORS
            or stage["error_field"] is not None
        ):
            raise ValueError("transport result differs")
        return None
    if stage["finish_reason"] == "length":
        if (
            raw is None
            or stage["status"] != "response_error"
            or stage["error_code"] != "finish_length"
            or stage["error_field"] is not None
        ):
            raise ValueError("truncated result differs")
        return None
    if stage["finish_reason"] != "stop" or raw is None:
        raise ValueError("response finish differs")
    try:
        if arm == "R":
            result = {"owner_to_target": _relation_only(raw), "hazard_owner_span": None}
        else:
            result = prior._raw_stage2(raw, message)
    except ValidationError as error:
        if (
            stage["status"] != "contract_error"
            or stage["error_code"] != error.code
            or stage["error_field"] != error.field
        ):
            raise ValueError("contract error differs") from None
        return None
    if (
        stage["status"] != "validated"
        or stage["error_code"] is not None
        or stage["error_field"] is not None
    ):
        raise ValueError("validated response metadata differs")
    return result


def audit_end(row: dict, case: dict, arm: str, private_dir: Path) -> dict:
    if type(row) is not dict or set(row) != END_KEYS or row["event"] != "end":
        raise ValueError("journal end fields differ")
    if row["case_id"] != case["id"] or row["arm"] != arm:
        raise ValueError("journal case or arm identity differs")
    stages = row["stage2"]
    events = case["events"]
    if type(stages) is not list or len(stages) != len(events):
        raise ValueError("Stage2 event alignment differs")
    message = case["user_message"]
    clauses = split_clauses(message)
    relations: list[str | None] = []
    owners: list[dict | None] = []
    failed = False
    for index, (event, stage) in enumerate(zip(events, stages, strict=True), 1):
        if type(stage) is not dict or set(stage) != STAGE_KEYS:
            raise ValueError("Stage2 fields differ")
        if type(stage["event_index"]) is not int or stage["event_index"] != index:
            raise ValueError("Stage2 event index differs")
        anchored = anchor_span(event["event_span"], clauses, field="event_span")
        if (
            stage["event_span"] != prior._public_span(anchored)
            or stage["occurrence"] != event["occurrence"]
        ):
            raise ValueError("oracle event input differs")
        called = event["occurrence"] != "nonoccurring" and (
            arm != "O" or event["hazard_owner_span"] is not None
        )
        skip_reason = (
            None
            if called
            else "nonoccurring"
            if event["occurrence"] == "nonoccurring"
            else "owner_oracle_unavailable"
        )
        prior._check_common(stage, called=called, skip_reason=skip_reason)
        raw = prior._read_raw(stage, private_dir / f"{arm}-{case['id']}-stage2-{index}.json.txt")
        if not called:
            if stage["owner_to_target"] is not None or stage["hazard_owner_span"] is not None:
                raise ValueError("skipped Stage2 decision differs")
            if skip_reason == "owner_oracle_unavailable":
                failed = True
            relations.append(None)
            owners.append(None)
            continue
        result = _replay(stage, raw, arm=arm, message=message)
        if result is None:
            if stage["owner_to_target"] is not None or stage["hazard_owner_span"] is not None:
                raise ValueError("invalid Stage2 decision differs")
            failed = True
            relations.append(None)
            owners.append(None)
        else:
            public_owner = prior._public_span(result["hazard_owner_span"])
            if (
                stage["owner_to_target"] != result["owner_to_target"]
                or stage["hazard_owner_span"] != public_owner
            ):
                raise ValueError("Stage2 public decision differs")
            relations.append(result["owner_to_target"])
            owners.append(public_owner)
    route = prior._route(events, relations, overflow=case["overflow"], failed=failed)
    calls = sum(stage["called"] for stage in stages)
    call_sum = round(sum(stage["request_latency_ms"] or 0 for stage in stages), 3)
    stage_sum = round(sum(stage["latency_ms"] or 0 for stage in stages), 3)
    if (
        row["route"] != route
        or type(row["request_count"]) is not int
        or row["request_count"] != calls
        or not prior._duration(row["elapsed_ms"])
        or row["model_call_latency_sum_ms"] != call_sum
        or row["elapsed_ms"] + 0.01 < stage_sum
    ):
        raise ValueError("journal route or call metrics differ")
    return {
        "case_id": case["id"],
        "route": route,
        "request_count": calls,
        "relations": relations,
        "owner_spans": owners,
        "stage2_statuses": [stage["status"] for stage in stages],
        "stage2_called": [stage["called"] for stage in stages],
        "request_latencies_ms": [
            stage["request_latency_ms"] for stage in stages if stage["called"]
        ],
        "elapsed_ms": row["elapsed_ms"],
    }


def _percentiles(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    ordered = sorted(values)
    return (
        round(statistics.median(ordered), 3),
        round(ordered[math.ceil(len(ordered) * 0.95) - 1], 3),
    )


def summarize_arm(audited: list[dict], cases: list[dict], arm: str) -> dict:
    if len(audited) != len(cases) or any(
        result["case_id"] != case["id"] for result, case in zip(audited, cases, strict=True)
    ):
        raise ValueError("summary case order differs")
    category_counts = {key: 0 for key in CATEGORIES}
    category_relation_correct = {key: 0 for key in CATEGORIES}
    relation_by_case: dict[str, bool] = {}
    for result, case in zip(audited, cases, strict=True):
        all_correct = True
        for index, event in enumerate(case["events"]):
            if not result["stage2_called"][index]:
                continue
            category = f"{event['occurrence']}_{event['owner_to_target']}"
            if category not in category_counts:
                raise ValueError("unexpected gold relation category")
            category_counts[category] += 1
            correct = (
                result["stage2_statuses"][index] == "validated"
                and result["relations"][index] == event["owner_to_target"]
            )
            category_relation_correct[category] += correct
            all_correct &= correct
        relation_by_case[case["id"]] = all_correct
    by_id = {case["id"]: (result, case) for result, case in zip(audited, cases, strict=True)}
    pairs_correct = sum(
        all(
            relation_by_case[case_id]
            and by_id[case_id][0]["route"] == by_id[case_id][1]["expected_route"]
            for case_id in pair
        )
        for pair in CONTRAST_PAIRS
        if all(case_id in by_id for case_id in pair)
    )
    request_p50, request_p95 = _percentiles(
        [latency for result in audited for latency in result["request_latencies_ms"]]
    )
    elapsed_p50, elapsed_p95 = _percentiles([result["elapsed_ms"] for result in audited])

    def other(case: dict) -> bool:
        return case["expected_route"] == NORMAL and any(
            event["occurrence"] == "observed" and event["owner_to_target"] == "other"
            for event in case["events"]
        )

    called = [stage for result in audited for stage in result["stage2_called"]]
    statuses = [status for result in audited for status in result["stage2_statuses"]]
    return {
        "cases": len(cases),
        "gold_event_count": sum(len(case["events"]) for case in cases),
        "eligible_gold_event_count": sum(called),
        "skip_nonoccurring": sum(
            event["occurrence"] == "nonoccurring" for case in cases for event in case["events"]
        ),
        "skip_owner_unavailable": sum(
            arm == "O"
            and event["occurrence"] != "nonoccurring"
            and event["hazard_owner_span"] is None
            for case in cases
            for event in case["events"]
        ),
        "relation_correct": sum(category_relation_correct.values()),
        "category_counts": category_counts,
        "category_relation_correct": category_relation_correct,
        "route_correct_all": sum(
            result["route"] == case["expected_route"]
            for result, case in zip(audited, cases, strict=True)
        ),
        "model_involved_cases": sum(result["request_count"] > 0 for result in audited),
        "model_involved_route_correct": sum(
            result["request_count"] > 0 and result["route"] == case["expected_route"]
            for result, case in zip(audited, cases, strict=True)
        ),
        "multi_event_cases": sum(len(case["events"]) > 1 for case in cases),
        "multi_event_route_correct": sum(
            len(case["events"]) > 1 and result["route"] == case["expected_route"]
            for result, case in zip(audited, cases, strict=True)
        ),
        "contrast_pair_count": sum(
            all(case_id in by_id for case_id in pair) for pair in CONTRAST_PAIRS
        ),
        "contrast_pairs_correct": pairs_correct,
        "other_observed_cases": sum(other(case) for case in cases),
        "false_direct_other": sum(
            other(case) and result["route"] == "safety_action_required"
            for result, case in zip(audited, cases, strict=True)
        ),
        "missed_direct_current": sum(
            case["expected_route"] == "safety_action_required"
            and result["route"] != "safety_action_required"
            for result, case in zip(audited, cases, strict=True)
        ),
        "unnecessary_confirm": sum(
            case["expected_route"] == NORMAL and result["route"] == "confirming_safety_status"
            for result, case in zip(audited, cases, strict=True)
        ),
        "stage2_errors": sum(
            was_called and status != "validated"
            for was_called, status in zip(called, statuses, strict=True)
        ),
        "request_count": sum(result["request_count"] for result in audited),
        "stage2_valid": sum(
            was_called and status == "validated"
            for was_called, status in zip(called, statuses, strict=True)
        ),
        "case_elapsed_p50_ms": elapsed_p50,
        "case_elapsed_p95_ms": elapsed_p95,
        "request_latency_p50_ms": request_p50,
        "request_latency_p95_ms": request_p95,
    }


def baseline_paired(baseline_private_dir: Path, model_path: Path) -> dict:
    verified = prior.verify(
        BASELINE_PROTOCOL, BASELINE_JOURNAL, baseline_private_dir, model_path=model_path
    )
    stored = parse_model_json(BASELINE_VERIFICATION.read_text(encoding="utf-8"))
    if verified != stored:
        raise ValueError("prior independent verification differs")
    cases = load_cases(DATASET)
    rows = [
        parse_model_json(line) for line in BASELINE_JOURNAL.read_text(encoding="utf-8").splitlines()
    ]
    audited = [
        prior.audit_end(rows[2 + 2 * index], case, baseline_private_dir)
        for index, case in enumerate(cases)
    ]
    available_correct = 0
    available_events = 0
    for result, case in zip(audited, cases, strict=True):
        for index, event in enumerate(case["events"]):
            if event["occurrence"] == "nonoccurring" or event["hazard_owner_span"] is None:
                continue
            available_events += 1
            available_correct += (
                result["stage2_statuses"][index] == "validated"
                and result["relations"][index] == event["owner_to_target"]
            )
    available_model_cases = [
        (result, case)
        for result, case in zip(audited, cases, strict=True)
        if result["request_count"] > 0
        and all(
            event["hazard_owner_span"] is not None
            for event in case["events"]
            if event["occurrence"] != "nonoccurring"
        )
    ]
    return {
        "relation_correct_all": verified["relation_correct"],
        "relation_correct_owner_available": available_correct,
        "model_involved_route_correct_all": verified["model_involved_route_correct"],
        "model_involved_route_correct_owner_available": sum(
            result["route"] == case["expected_route"] for result, case in available_model_cases
        ),
        "owner_available_event_count": available_events,
        "owner_available_model_involved_cases": len(available_model_cases),
    }


def verify(
    protocol_path: Path,
    journal_path: Path,
    private_dir: Path,
    baseline_private_dir: Path,
    *,
    model_path: Path,
) -> dict:
    protocol, protocol_sha = check_protocol(protocol_path, model_path)
    prior._private_dir(private_dir)
    baseline = baseline_paired(baseline_private_dir, model_path)
    cases = load_cases(DATASET)
    rows = [
        parse_model_json(line) for line in journal_path.read_text(encoding="utf-8").splitlines()
    ]
    if len(rows) != 2 + 2 * len(cases) * len(ARMS):
        raise ValueError("journal row count differs")
    if rows[0] != {"event": "header", "protocol_sha256": protocol_sha}:
        raise ValueError("journal header differs")
    audited: dict[str, list[dict]] = {}
    expected_files: set[str] = set()
    offset = 1
    for arm in ARMS:
        arm_audit = []
        for case in cases:
            if rows[offset] != {"event": "begin", "arm": arm, "case_id": case["id"]}:
                raise ValueError("journal arm or case order differs")
            row = rows[offset + 1]
            arm_audit.append(audit_end(row, case, arm, private_dir))
            expected_files.update(
                f"{arm}-{case['id']}-stage2-{stage['event_index']}.json.txt"
                for stage in row["stage2"]
                if stage["raw_sha256"] is not None
            )
            offset += 2
        audited[arm] = arm_audit
    if {item.name for item in private_dir.iterdir()} != expected_files:
        raise ValueError("private raw file inventory differs")
    summary = {
        "event": "summary",
        "arms": {arm: summarize_arm(audited[arm], cases, arm) for arm in ARMS},
        "baseline_paired": baseline,
    }
    if rows[-1] != summary:
        raise ValueError("journal summary differs")
    return {
        "kind": KIND,
        "claim_scope": SCOPE,
        "protocol_sha256": protocol_sha,
        "journal_sha256": prior._digest(journal_path.read_bytes()),
        "arms": summary["arms"],
        "baseline_paired": baseline,
        "model_sha256": protocol["model_sha256"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--private-dir", required=True, type=Path)
    parser.add_argument("--baseline-private-dir", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            verify(
                args.protocol,
                args.journal,
                args.private_dir,
                args.baseline_private_dir,
                model_path=args.model_path,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
