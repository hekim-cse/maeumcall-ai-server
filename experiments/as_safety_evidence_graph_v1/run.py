"""Run a frozen ES event-oracle evidence-graph diagnostic locally.

Reviewed A, E and occurrence enter prompts. Reviewed B, relation, route and
new edge labels are used only after model calls for scoring. No partial run is
resumed or overwritten; interrupted outputs require manual audit.
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

from experiments.as_safety_v2.evidence_graph import (
    ATTACHMENT_KINDS,
    EDGE_KINDS,
    evidence_graph_messages,
    evidence_graph_schema,
    validate_evidence_graph,
)
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.transport import RequestPolicy, post_json_completion
from experiments.as_safety_v4 import run as v4
from experiments.as_safety_v4.cases import load_cases
from experiments.as_safety_v4.contract import route_for_events
from scripts.build_as_safety_evidence_graph_labels import compile_labels

ROOT = v4.ROOT
KIND = "as_safety_evidence_graph_v1_development_v1"
SCOPE = "already_exposed_ai_authored_event_oracle_graph_development_only"
CASE_ORDER = v4.CASE_ORDER
IMAGE = v4.IMAGE
MODEL_SHA = v4.MODEL_SHA
RUNTIME = v4.RUNTIME
REQUEST = v4.REQUEST
DATA = v4.DATA
INPUTS = {
    "dataset": v4.INPUTS["dataset"],
    "review": v4.INPUTS["review"],
    "field_review": v4.INPUTS["field_review"],
    "graph_method": ROOT / "docs/portfolio/nlu_safety_evidence_graph_v1_method.md",
    "graph_field_review": ROOT / "docs/portfolio/nlu_safety_evidence_graph_v1_field_review.md",
    "graph_labels": DATA / "as-safety-evidence-graph-v1-development-reviewed.v1.json",
}
PROTOCOL_FIELDS = v4.PROTOCOL_FIELDS
REQUIRED_SOURCES = v4.REQUIRED_V4_SOURCES | {
    "experiments/as_safety_evidence_graph_v1/__init__.py",
    "experiments/as_safety_evidence_graph_v1/run.py",
    "experiments/as_safety_evidence_graph_v1/verify.py",
    "scripts/build_as_safety_evidence_graph_labels.py",
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
    paths: set[str] = set()
    for prefix in (
        "experiments/as_safety_v2",
        "experiments/as_safety_v4",
        "experiments/as_safety_evidence_graph_v1",
        "scripts/build_as_safety_evidence_graph_labels.py",
    ):
        output = v4._git("ls-tree", "-r", "--name-only", commit, "--", prefix)
        paths.update(path for path in output.decode().splitlines() if path.endswith(".py"))
    return paths


def load_graph_labels(
    path: Path,
    cases: list[dict],
    *,
    expected_sha: str | None = None,
    review_path: Path | None = None,
) -> list[dict]:
    """Validate approved new labels against existing reviewed ES case order.

    Exact source anchoring checks provenance, not correctness of the proposed
    attachment or typed edge. Human approval remains the semantic boundary.
    """
    raw = path.read_bytes()
    if expected_sha is not None and v4.digest(raw) != expected_sha:
        raise ValueError("graph labels changed after protocol check")
    labels = json.loads(raw)
    if (
        type(labels) is not dict
        or set(labels) != {"kind", "review_status", "review_sha256", "cases"}
        or labels["kind"] != "as_safety_evidence_graph_v1_labels"
        or labels["review_status"] != "owner_approved_for_exploratory_evaluation"
        or type(labels["cases"]) is not list
        or len(labels["cases"]) != len(cases)
    ):
        raise ValueError("graph labels are not approved and ordered")
    if (
        type(labels["review_sha256"]) is not str
        or v4.SHA_RE.fullmatch(labels["review_sha256"]) is None
        or review_path is not None
        and labels["review_sha256"] != v4.digest_file(review_path)
    ):
        raise ValueError("graph labels differ from reviewed table")
    for item, case in zip(labels["cases"], cases, strict=True):
        if (
            type(item) is not dict
            or set(item) != {"id", "events"}
            or item["id"] != case["id"]
            or type(item["events"]) is not list
            or len(item["events"]) != len(case["events"])
        ):
            raise ValueError("graph case labels differ")
        for index, (label, event) in enumerate(zip(item["events"], case["events"], strict=True), 1):
            if (
                type(label) is not dict
                or set(label)
                != {
                    "event_index",
                    "event_subject_kind",
                    "event_subject_evidence_span",
                    "target_edge_kind",
                    "target_edge_evidence_span",
                }
                or type(label["event_index"]) is not int
                or label["event_index"] != index
            ):
                raise ValueError("graph event label fields differ")
            fields = (
                "event_subject_kind",
                "event_subject_evidence_span",
                "target_edge_kind",
                "target_edge_evidence_span",
            )
            if event["occurrence"] == "nonoccurring":
                if any(label[field] is not None for field in fields):
                    raise ValueError("nonoccurring graph labels must be null")
                continue
            if (
                type(label["event_subject_kind"]) is not str
                or label["event_subject_kind"] not in ATTACHMENT_KINDS
                or type(label["target_edge_kind"]) is not str
                or label["target_edge_kind"] not in EDGE_KINDS
            ):
                raise ValueError("graph label kind differs")
            subject_null = event["hazard_owner_span"] is None
            if subject_null != (label["event_subject_kind"] == "unresolved"):
                raise ValueError("graph attachment differs from approved subject")
            if subject_null and label["target_edge_kind"] != "unresolved":
                raise ValueError("graph edge differs from approved unknown")
            try:
                decision = validate_evidence_graph(
                    json.dumps(
                        {
                            "subject_span": event["hazard_owner_span"],
                            "event_subject_kind": label["event_subject_kind"],
                            "event_subject_evidence_span": label["event_subject_evidence_span"],
                            "target_edge_kind": label["target_edge_kind"],
                            "target_edge_evidence_span": label["target_edge_evidence_span"],
                        },
                        ensure_ascii=False,
                    ),
                    case["user_message"],
                    event["event_span"],
                    event["occurrence"],
                    product_index=case["target"]["clause_index"],
                    target_mention=case["target"]["quote"],
                )
            except ValidationError as error:
                raise ValueError("graph label source structure differs") from error
            if decision["effective_relation"] != event["owner_to_target"]:
                raise ValueError("graph label relation differs from approved relation")
    if review_path is not None and labels != compile_labels(approved=True, review_path=review_path):
        raise ValueError("graph labels differ from reviewed table values")
    return labels["cases"]


def load_protocol(path: Path, model_path: Path) -> tuple[dict, str]:
    """Refuse requests until code, approved inputs, model and protocol are frozen."""
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
    load_graph_labels(
        INPUTS["graph_labels"],
        load_cases(INPUTS["dataset"]),
        expected_sha=hashes["graph_labels"],
        review_path=INPUTS["graph_field_review"],
    )
    sources = _source_paths(commit)
    if not REQUIRED_SOURCES <= sources:
        raise ValueError("required graph source missing from frozen commit")
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


def call_case(
    case: dict,
    policy: RequestPolicy,
    private_dir: Path,
    *,
    completion_call: CompletionCall = post_json_completion,
) -> dict:
    """Call once per actionable reviewed event; never send gold B/relation/route."""
    started = time.perf_counter()
    message = case["user_message"]
    target = {
        "product_index": case["target"]["clause_index"],
        "target_mention": case["target"]["quote"],
    }
    clauses = split_clauses(message)
    stages: list[dict] = []
    route_events: list[dict] = []
    relations: list[str | None] = []
    failed = False
    for index, gold in enumerate(case["events"], 1):
        event_span = anchor_span(gold["event_span"], clauses, field="event_span")
        occurrence = gold["occurrence"]
        route_events.append({"event_span": event_span, "occurrence": occurrence})
        public = {
            "event_index": index,
            "event_span": v4._public_span(event_span),
            "occurrence": occurrence,
            "subject_span": None,
            "event_subject_kind": None,
            "event_subject_evidence_span": None,
            "target_edge_kind": None,
            "target_edge_evidence_span": None,
            "effective_relation": None,
        }
        if occurrence == "nonoccurring":
            stages.append({**v4._blank(called=False, skip_reason="nonoccurring"), **public})
            relations.append(None)
            continue
        stage, raw = v4._call(
            messages=evidence_graph_messages(message, gold["event_span"], occurrence, **target),
            schema=evidence_graph_schema(message),
            policy=policy,
            raw_path=private_dir / f"{case['id']}-graph-{index}.json.txt",
            completion_call=completion_call,
        )
        stage.update(public)
        if stage["error_code"] is None and raw is not None:
            try:
                decision = validate_evidence_graph(
                    raw, message, gold["event_span"], occurrence, **target
                )
            except ValidationError as error:
                stage.update(
                    status="contract_error", error_code=error.code, error_field=error.field
                )
            else:
                stage.update(
                    status="validated",
                    subject_span=v4._public_span(decision["subject_span"]),
                    event_subject_kind=decision["event_subject_kind"],
                    event_subject_evidence_span=v4._public_span(
                        decision["event_subject_evidence_span"]
                    ),
                    target_edge_kind=decision["target_edge_kind"],
                    target_edge_evidence_span=v4._public_span(
                        decision["target_edge_evidence_span"]
                    ),
                    effective_relation=decision["effective_relation"],
                )
        if stage["status"] != "validated":
            failed = True
        stages.append(stage)
        relations.append(stage["effective_relation"])
    route = route_for_events(route_events, relations, overflow=case["overflow"], failed=failed)
    return {
        "event": "end",
        "case_id": case["id"],
        "stages": stages,
        "route": route,
        "request_count": sum(int(stage["called"]) for stage in stages),
        "model_call_latency_sum_ms": round(
            sum(stage["request_latency_ms"] or 0 for stage in stages), 3
        ),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def summarize(rows: list[dict], cases: list[dict], labels: list[dict]) -> dict:
    """Keep strict source-span and typed-edge scores separate from route scores."""
    if (
        len(rows) != len(cases)
        or tuple(row["case_id"] for row in rows) != tuple(case["id"] for case in cases)
        or len(labels) != len(cases)
    ):
        raise ValueError("case count or order differs")
    elapsed = sorted(row["elapsed_ms"] for row in rows)
    request_latency = sorted(
        stage["request_latency_ms"] for row in rows for stage in row["stages"] if stage["called"]
    )
    category_counts = dict.fromkeys(RELATION_CATEGORIES, 0)
    category_relation_correct = dict.fromkeys(RELATION_CATEGORIES, 0)
    relation_correct = 0
    subject_exact_nonnull = 0
    subject_null_correct = 0
    attachment_kind_correct = 0
    attachment_evidence_exact = 0
    edge_kind_correct = 0
    edge_evidence_exact = 0
    label_joint_correct = 0
    all_fields_exact = 0
    attachment_evidence_gold_nonnull_count = 0
    edge_evidence_gold_nonnull_count = 0
    case_relation_correct = {}
    for row, case, label_case in zip(rows, cases, labels, strict=True):
        if label_case["id"] != case["id"] or len(label_case["events"]) != len(case["events"]):
            raise ValueError("graph labels differ from case order")
        clauses = split_clauses(case["user_message"])
        all_correct = True
        for stage, gold, label in zip(
            row["stages"], case["events"], label_case["events"], strict=True
        ):
            if gold["occurrence"] == "nonoccurring":
                continue
            category = f"{gold['occurrence']}_{gold['owner_to_target']}"
            if category not in category_counts:
                raise ValueError("gold relation category differs")
            category_counts[category] += 1
            correct = (
                stage["status"] == "validated"
                and stage["effective_relation"] == gold["owner_to_target"]
            )
            category_relation_correct[category] += correct
            relation_correct += correct
            all_correct &= correct
            valid = stage["status"] == "validated"
            predicted_subject = stage["subject_span"]
            gold_subject = anchor_span(gold["hazard_owner_span"], clauses, field="subject_span")
            gold_subject_public = v4._public_span(gold_subject)
            subject_match = valid and predicted_subject == gold_subject_public
            if gold["hazard_owner_span"] is not None:
                subject_exact_nonnull += subject_match
            else:
                subject_null_correct += subject_match
            attachment_match = valid and stage["event_subject_kind"] == label["event_subject_kind"]
            edge_match = valid and stage["target_edge_kind"] == label["target_edge_kind"]
            attachment_kind_correct += attachment_match
            edge_kind_correct += edge_match
            span_matches = []
            for field in ("event_subject_evidence_span", "target_edge_evidence_span"):
                expected_span = anchor_span(label[field], clauses, field=field)
                if expected_span is not None:
                    if field == "event_subject_evidence_span":
                        attachment_evidence_gold_nonnull_count += 1
                    else:
                        edge_evidence_gold_nonnull_count += 1
                match = valid and stage[field] == v4._public_span(expected_span)
                span_matches.append(match)
                if expected_span is not None and match:
                    if field == "event_subject_evidence_span":
                        attachment_evidence_exact += 1
                    else:
                        edge_evidence_exact += 1
            joint = subject_match and attachment_match and edge_match and correct
            label_joint_correct += joint
            all_fields_exact += joint and all(span_matches)
        case_relation_correct[case["id"]] = all_correct
    case_routes_correct = {
        case["id"]: row["route"] == case["expected_route"]
        for row, case in zip(rows, cases, strict=True)
    }
    eligible_pairs = [
        pair for pair in CONTRAST_PAIRS if all(case_id in case_routes_correct for case_id in pair)
    ]
    pairs_correct = sum(
        all(case_relation_correct[case_id] and case_routes_correct[case_id] for case_id in pair)
        for pair in eligible_pairs
    )
    normal = "collecting_service_request"
    return {
        "cases": len(rows),
        "gold_event_count": sum(len(case["events"]) for case in cases),
        "actionable_gold_event_count": sum(
            gold["occurrence"] != "nonoccurring" for case in cases for gold in case["events"]
        ),
        "relation_correct": relation_correct,
        "subject_exact_nonnull": subject_exact_nonnull,
        "subject_null_correct": subject_null_correct,
        "subject_gold_nonnull_count": sum(
            event["occurrence"] != "nonoccurring" and event["hazard_owner_span"] is not None
            for case in cases
            for event in case["events"]
        ),
        "subject_gold_null_count": sum(
            event["occurrence"] != "nonoccurring" and event["hazard_owner_span"] is None
            for case in cases
            for event in case["events"]
        ),
        "attachment_kind_correct": attachment_kind_correct,
        "attachment_evidence_exact": attachment_evidence_exact,
        "attachment_evidence_gold_nonnull_count": attachment_evidence_gold_nonnull_count,
        "edge_kind_correct": edge_kind_correct,
        "edge_evidence_exact": edge_evidence_exact,
        "edge_evidence_gold_nonnull_count": edge_evidence_gold_nonnull_count,
        "label_joint_correct": label_joint_correct,
        "all_fields_exact": all_fields_exact,
        "category_counts": category_counts,
        "category_relation_correct": category_relation_correct,
        "route_correct": sum(case_routes_correct.values()),
        "model_involved_cases": sum(row["request_count"] > 0 for row in rows),
        "model_involved_route_correct": sum(
            row["request_count"] > 0 and case_routes_correct[row["case_id"]] for row in rows
        ),
        "multi_event_cases": sum(len(case["events"]) > 1 for case in cases),
        "multi_event_route_correct": sum(
            len(case["events"]) > 1 and case_routes_correct[case["id"]]
            for row, case in zip(rows, cases, strict=True)
        ),
        "contrast_pair_count": len(eligible_pairs),
        "contrast_pairs_correct": pairs_correct,
        "missed_direct_current": sum(
            case["expected_route"] == "safety_action_required"
            and row["route"] != "safety_action_required"
            for row, case in zip(rows, cases, strict=True)
        ),
        "false_direct_other": sum(
            case["expected_route"] == normal
            and row["route"] == "safety_action_required"
            and any(
                event["occurrence"] == "observed" and event["owner_to_target"] == "other"
                for event in case["events"]
            )
            for row, case in zip(rows, cases, strict=True)
        ),
        "unnecessary_confirm": sum(
            case["expected_route"] == normal and row["route"] == "confirming_safety_status"
            for row, case in zip(rows, cases, strict=True)
        ),
        "graph_errors": sum(
            stage["called"] and stage["status"] != "validated"
            for row in rows
            for stage in row["stages"]
        ),
        "request_count": sum(row["request_count"] for row in rows),
        "graph_valid": sum(
            stage["status"] == "validated" for row in rows for stage in row["stages"]
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
    labels = load_graph_labels(
        INPUTS["graph_labels"],
        cases,
        expected_sha=protocol["input_hashes"]["graph_labels"],
        review_path=INPUTS["graph_field_review"],
    )
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
    rows: list[dict] = []
    with args.output.open("x", encoding="utf-8") as stream:
        v4._append(stream, {"event": "header", "protocol_sha256": protocol_sha})
        for case in cases:
            v4._append(stream, {"event": "begin", "case_id": case["id"]})
            row = call_case(case, policy, args.private_dir, completion_call=completion_call)
            v4._append(stream, row)
            rows.append(row)
        v4._append(stream, {"event": "summary", **summarize(rows, cases, labels)})


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
