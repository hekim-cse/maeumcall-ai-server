"""Freeze and replay the exposed ES lexical relation baseline without a model."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from experiments.as_safety_explicit_baseline_v1.contract import predict_relation
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v4.cases import load_cases
from experiments.as_safety_v4.contract import route_for_events

ROOT = Path(__file__).resolve().parents[1]
DATASET = (
    ROOT
    / "evals/structured_nlu/data/ai_heldout/as-safety-event-source-v4-exploration-reviewed.v1.json"
)
PATHS = (
    "experiments/as_safety_explicit_baseline_v1/__init__.py",
    "experiments/as_safety_explicit_baseline_v1/contract.py",
    "experiments/as_safety_v2/extraction.py",
    "experiments/as_safety_v2/json_contract.py",
    "experiments/as_safety_v2/quotes.py",
    "experiments/as_safety_v4/cases.py",
    "experiments/as_safety_v4/contract.py",
    "scripts/run_as_safety_explicit_baseline_v1.py",
    "tests/test_as_safety_explicit_baseline_v1.py",
    "docs/portfolio/nlu_safety_explicit_baseline_v1_method.md",
    "docs/portfolio/nlu_safety_event_source_v4_review.md",
    "docs/portfolio/nlu_safety_event_source_v4_field_review.md",
    DATASET.relative_to(ROOT).as_posix(),
)
PAIRS = (("ES01", "ES09"), ("ES02", "ES11"))


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def _committed(commit: str, relative: str) -> bytes:
    return _git("show", f"{commit}:{relative}")


def _cases() -> list[dict]:
    cases = load_cases(DATASET)
    if tuple(case["id"] for case in cases) != tuple(f"ES{i:02}" for i in range(1, 21)):
        raise ValueError("ES case order differs")
    return cases


def prepare(output: Path) -> None:
    if _git("status", "--porcelain").strip():
        raise ValueError("commit code and inputs before preparing protocol")
    output.resolve().relative_to(ROOT)
    commit = _git("rev-parse", "HEAD").decode().strip()
    hashes = {}
    for relative in PATHS:
        raw = (ROOT / relative).read_bytes()
        if raw != _committed(commit, relative):
            raise ValueError(f"source differs from committed bytes: {relative}")
        hashes[relative] = _sha(raw)
    cases = _cases()
    protocol = {
        "kind": "as_safety_explicit_baseline_v1_exposed_development",
        "claim_scope": "reviewed_A_E_B_oracle_exposed_ES_not_official_accuracy",
        "frozen_code_commit": commit,
        "source_input_sha256": hashes,
        "case_order": [case["id"] for case in cases],
        "event_order": [
            f"{case['id']}-{index}" for case in cases for index, _ in enumerate(case["events"], 1)
        ],
        "contrast_pairs": [list(pair) for pair in PAIRS],
        "model_calls": 0,
        "retry_policy": "no_retry_version_on_error",
    }
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n")


def _checked_protocol(path: Path) -> tuple[dict, str, list[dict]]:
    raw = path.read_bytes()
    protocol = json.loads(raw)
    if type(protocol) is not dict or set(protocol) != {
        "kind",
        "claim_scope",
        "frozen_code_commit",
        "source_input_sha256",
        "case_order",
        "event_order",
        "contrast_pairs",
        "model_calls",
        "retry_policy",
    }:
        raise ValueError("protocol fields differ")
    commit = protocol["frozen_code_commit"]
    if (
        type(commit) is not str
        or re.fullmatch(r"[0-9a-f]{40}", commit) is None
        or protocol["kind"] != "as_safety_explicit_baseline_v1_exposed_development"
        or protocol["claim_scope"] != "reviewed_A_E_B_oracle_exposed_ES_not_official_accuracy"
        or protocol["model_calls"] != 0
        or protocol["retry_policy"] != "no_retry_version_on_error"
        or protocol["contrast_pairs"] != [list(pair) for pair in PAIRS]
        or set(protocol["source_input_sha256"]) != set(PATHS)
    ):
        raise ValueError("protocol identity differs")
    for relative in PATHS:
        frozen = _committed(commit, relative)
        if _sha(frozen) != protocol["source_input_sha256"][relative]:
            raise ValueError(f"frozen source digest differs: {relative}")
        if (ROOT / relative).read_bytes() != frozen:
            raise ValueError(f"source differs from frozen commit: {relative}")
    cases = _cases()
    if protocol["case_order"] != [case["id"] for case in cases] or protocol["event_order"] != [
        f"{case['id']}-{i}" for case in cases for i, _ in enumerate(case["events"], 1)
    ]:
        raise ValueError("case or event order differs")
    relative_protocol = path.resolve().relative_to(ROOT).as_posix()
    if _git("show", f"HEAD:{relative_protocol}") != raw:
        raise ValueError("commit protocol before evaluating")
    return protocol, _sha(raw), cases


def evaluate(protocol_path: Path) -> dict:
    protocol, protocol_sha, cases = _checked_protocol(protocol_path)
    rows = []
    routes = {}
    for case in cases:
        relations = []
        failed = False
        for index, event in enumerate(case["events"], 1):
            try:
                prediction = predict_relation(
                    case["user_message"],
                    target=case["target"],
                    event_span=event["event_span"],
                    hazard_owner_span=event["hazard_owner_span"],
                    occurrence=event["occurrence"],
                )
                error_code = None
            except ValidationError as error:
                prediction = {
                    "relation": None if event["occurrence"] == "nonoccurring" else "unknown",
                    "basis": "error",
                }
                error_code = error.code
                failed = True
            except Exception:
                # Do not publish exception text, which may contain source excerpts.
                prediction = {
                    "relation": None if event["occurrence"] == "nonoccurring" else "unknown",
                    "basis": "error",
                }
                error_code = "unexpected_exception"
                failed = True
            relations.append(prediction["relation"])
            rows.append(
                {
                    "event_id": f"{case['id']}-{index}",
                    "occurrence": event["occurrence"],
                    "gold_relation": event["owner_to_target"],
                    "predicted_relation": prediction["relation"],
                    "basis": prediction["basis"],
                    "error_code": error_code,
                }
            )
        routes[case["id"]] = route_for_events(
            [{"occurrence": event["occurrence"]} for event in case["events"]],
            relations,
            overflow=case["overflow"],
            failed=failed,
        )
    actionable = [row for row in rows if row["occurrence"] != "nonoccurring"]
    if len(rows) != 22 or len(actionable) != 19:
        raise ValueError("ES denominator differs")
    categories = {
        "observed_current": ("observed", "current", 8),
        "observed_other": ("observed", "other", 9),
        "observed_unknown": ("observed", "unknown", 1),
        "uncertain_current": ("uncertain", "current", 1),
    }
    category_counts = {}
    for name, (occurrence, relation, expected) in categories.items():
        selected = [
            row
            for row in actionable
            if (row["occurrence"], row["gold_relation"]) == (occurrence, relation)
        ]
        if len(selected) != expected:
            raise ValueError(f"gold category denominator differs: {name}")
        category_counts[name] = {
            "correct": sum(row["predicted_relation"] == relation for row in selected),
            "total": expected,
        }
    decided = [row for row in actionable if row["predicted_relation"] in {"current", "other"}]
    relation_correct = sum(row["predicted_relation"] == row["gold_relation"] for row in actionable)
    route_correct = sum(routes[case["id"]] == case["expected_route"] for case in cases)
    missed = [
        row
        for row in actionable
        if row["occurrence"] == "observed"
        and row["gold_relation"] == "current"
        and row["predicted_relation"] != "current"
    ]
    missed_cases = {
        row["event_id"].split("-")[0]
        for row in missed
        if routes[row["event_id"].split("-")[0]] != "safety_action_required"
    }
    false_direct_cases = [
        case["id"]
        for case in cases
        if any(
            event["occurrence"] == "observed" and event["owner_to_target"] == "other"
            for event in case["events"]
        )
        and not any(
            event["occurrence"] == "observed" and event["owner_to_target"] == "current"
            for event in case["events"]
        )
        and routes[case["id"]] == "safety_action_required"
    ]
    by_case = {case["id"]: case for case in cases}
    by_event = {row["event_id"]: row for row in rows}
    pair_correct = sum(
        all(
            routes[case_id] == by_case[case_id]["expected_route"]
            and all(
                by_event[f"{case_id}-{index}"]["predicted_relation"] == event["owner_to_target"]
                for index, event in enumerate(by_case[case_id]["events"], 1)
            )
            for case_id in pair
        )
        for pair in PAIRS
    )
    errors = sum(row["error_code"] is not None for row in rows)
    gate = (
        all(item["correct"] == item["total"] for item in category_counts.values())
        and route_correct == 20
        and pair_correct == 2
        and errors == 0
    )
    return {
        "kind": "as_safety_explicit_baseline_v1_exposed_development_result",
        "protocol_sha256": protocol_sha,
        "frozen_code_commit": protocol["frozen_code_commit"],
        "claim_scope": protocol["claim_scope"],
        "summary": {
            "events": len(rows),
            "actionable_events": len(actionable),
            "relation_correct": relation_correct,
            "category_correct": category_counts,
            "relation_output": dict(Counter(row["predicted_relation"] for row in actionable)),
            "basis_output": dict(Counter(row["basis"] for row in rows)),
            "decided": len(decided),
            "decided_correct": sum(
                row["predicted_relation"] == row["gold_relation"] for row in decided
            ),
            "conditional_route_correct": route_correct,
            "conditional_route_total": len(cases),
            "missed_direct_current_events": len(missed),
            "missed_direct_current_cases": len(missed_cases),
            "false_direct_other_cases": false_direct_cases,
            "contrast_pairs_correct": pair_correct,
            "contrast_pairs_total": len(PAIRS),
            "errors": errors,
            "error_total": len(rows),
            "development_gate_passed": gate,
        },
        "events": rows,
        "routes": routes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "evaluate", "verify"))
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.protocol)
        return
    if args.result is None:
        parser.error("--result is required for evaluate or verify")
    result = evaluate(args.protocol)
    if args.command == "evaluate":
        with args.result.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    elif json.loads(args.result.read_text(encoding="utf-8")) != result:
        raise ValueError("saved result differs from deterministic replay")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
