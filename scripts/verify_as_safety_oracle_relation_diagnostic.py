"""Independently audit the exposed 24-call source-relation oracle journal."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from scripts.probe_as_safety_clause_index import split_clauses

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
SOURCES = {
    "runner_sha256": ROOT / "scripts/run_as_safety_oracle_relation_diagnostic.py",
    "candidate_sha256": ROOT / "scripts/probe_as_safety_oracle_relation.py",
    "completion_sha256": ROOT / "scripts/as_safety_completion_v2.py",
    "policy_loader_sha256": ROOT / "scripts/run_as_safety_compact_relation_development.py",
    "completion_type_sha256": ROOT / "scripts/as_safety_pair_executor_v2.py",
    "endpoint_guard_sha256": ROOT / "scripts/run_ai_heldout_pair.py",
    "request_policy_type_sha256": ROOT / "evals/structured_nlu/ai_heldout.py",
    "container_check_sha256": ROOT / "scripts/run_as_safety_event_gate_fresh.py",
    "case_loader_sha256": ROOT / "scripts/probe_as_safety_clause_index.py",
    "result_verifier_sha256": Path(__file__),
    "re_dataset_sha256": DATA / "as-safety-relation-fresh-reviewed.v1.json",
    "v_dataset_sha256": DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
    "spans_sha256": DATA / "as-safety-oracle-relation-spans-reviewed.v1.json",
    "policy_sha256": DATA / "as-safety-grounded-development-request.v1.json",
}
ACTIVE_IDS = tuple(
    [*(f"RE{index:02}" for index in range(1, 12))]
    + [*(f"V{index:02}" for index in range(1, 11)), "V12", "V14", "V16"]
)
DIRECT = "safety_action_required"
CONFIRM = "confirming_safety_status"
NORMAL = "collecting_service_request"
END_FIELDS = {
    "event",
    "case_id",
    "source_relation",
    "route",
    "error_stage",
    "error_type",
    "http_status",
    "finish_reason",
    "latency_ms",
}


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _active_cases() -> list[dict]:
    datasets = [
        json.loads(SOURCES[key].read_text(encoding="utf-8"))["cases"]
        for key in ("re_dataset_sha256", "v_dataset_sha256")
    ]
    all_cases = [case for dataset in datasets for case in dataset]
    if [case["id"] for case in all_cases] != [
        *(f"RE{index:02}" for index in range(1, 17)),
        *(f"V{index:02}" for index in range(1, 17)),
    ]:
        raise ValueError("RE/V case order differs")
    active = [
        case for case in all_cases if case["expected_relation"]["event_status"] != "nonoccurring"
    ]
    if len(active) != 24 or tuple(case["id"] for case in active) != ACTIVE_IDS:
        raise ValueError("active denominator differs")
    if any(
        case["expected_route"]
        != _route(
            case["expected_relation"]["target_relation"],
            case["expected_relation"]["event_status"],
        )
        for case in active
    ):
        raise ValueError("gold relation and route differ")
    return active


def _check_spans(cases: list[dict]) -> dict[str, dict]:
    payload = json.loads(SOURCES["spans_sha256"].read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or set(payload) != {"kind", "cases"}
        or payload["kind"] != "as_safety_oracle_relation_spans_reviewed_v1"
        or not isinstance(payload["cases"], list)
        or len(payload["cases"]) != 24
    ):
        raise ValueError("span document shape differs")
    interpretations = {}
    for case, span in zip(cases, payload["cases"], strict=True):
        required = {"id", "target_mention", "hazard_event_mention"}
        if case["id"] == "V04":
            required.add("reviewed_interpretation")
        if not isinstance(span, dict) or set(span) != required or span["id"] != case["id"]:
            raise ValueError("span order or fields differ")
        if case["id"] == "V04":
            interpretation = span["reviewed_interpretation"]
            if span["target_mention"] != "토스터" or interpretation != {
                "version": "v2_target_review",
                "target_relation": "current",
                "expected_route": "safety_action_required",
            }:
                raise ValueError("V04 reviewed interpretation differs")
            interpretations[case["id"]] = interpretation
        clauses = split_clauses(case["user_message"])
        gold = case["expected_relation"]
        if gold["event_status"] not in {"observed", "uncertain"} or gold["target_relation"] not in {
            "current",
            "other",
            "unknown",
        }:
            raise ValueError("active gold value differs")
        for name, index_name in (
            ("target_mention", "product_index"),
            ("hazard_event_mention", "hazard_index"),
        ):
            mention, clause_index = span[name], gold[index_name]
            if (
                not isinstance(mention, str)
                or not mention.strip()
                or type(clause_index) is not int
                or not 1 <= clause_index <= len(clauses)
                or clauses[clause_index - 1].count(mention) != 1
            ):
                raise ValueError("span does not uniquely anchor gold clause")
    return interpretations


def _route(source_relation: str, event_status: str) -> str:
    if source_relation == "other":
        return NORMAL
    if source_relation == "current" and event_status == "observed":
        return DIRECT
    return CONFIRM


def _check_end(row: dict, case: dict) -> None:
    if (
        not isinstance(row, dict)
        or set(row) != END_FIELDS
        or row["event"] != "end"
        or row["case_id"] != case["id"]
    ):
        raise ValueError("end row shape or order differs")
    latency = row["latency_ms"]
    if type(latency) not in {int, float} or not 0 <= latency < 86_400_000:
        raise ValueError("call latency differs")
    if row["finish_reason"] not in {None, "stop", "length"}:
        raise ValueError("finish reason differs")
    status = row["http_status"]
    if status is not None and (type(status) is not int or not 100 <= status <= 599):
        raise ValueError("HTTP status differs")
    if row["error_stage"] is None:
        if (
            row["error_type"] is not None
            or status is not None
            or row["finish_reason"] != "stop"
            or row["source_relation"] not in {"current", "other", "unknown"}
            or row["route"]
            != _route(row["source_relation"], case["expected_relation"]["event_status"])
        ):
            raise ValueError("successful relation decision differs")
        return
    if row["error_stage"] not in {"response", "contract"} or (
        not isinstance(row["error_type"], str)
        or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", row["error_type"])
    ):
        raise ValueError("error metadata differs")
    if row["source_relation"] is not None or row["route"] is not None:
        raise ValueError("failed response has a decision")
    if row["error_stage"] == "contract" and (row["finish_reason"] != "stop" or status is not None):
        raise ValueError("contract failure metadata differs")
    if status is not None and row["error_stage"] != "response":
        raise ValueError("HTTP failure stage differs")


def verify(protocol_path: Path, journal_path: Path) -> dict:
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    if (
        protocol.get("kind") != "as_safety_oracle_relation_diagnostic_v1"
        or protocol.get("claim_scope") != "already_exposed_ai_authored_oracle_diagnostic_only"
        or protocol.get("case_order") != "RE01-RE11,V01-V10,V12,V14,V16"
        or protocol.get("retry_policy") != "no_retry_manual_audit_on_interruption"
        or protocol.get("endpoint") != "http://127.0.0.1:18081/v1/chat/completions"
        or protocol.get("server_image_digest")
        != "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
        or protocol.get("max_tokens") != 180
        or protocol.get("local_runtime")
        != {
            "host_port": 18081,
            "cpu_count": 2,
            "memory_bytes": 4 * 1024**3,
            "context_tokens": 4096,
            "threads": 2,
            "parallel_slots": 1,
        }
        or not isinstance(protocol.get("model_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", protocol["model_sha256"])
    ):
        raise ValueError("oracle protocol differs")
    for key, path in SOURCES.items():
        if digest(path) != protocol.get(key):
            raise ValueError(f"frozen {key} differs")
    cases = _active_cases()
    interpretations = _check_spans(cases)
    gold_counts = Counter(
        interpretations.get(case["id"], {}).get(
            "target_relation", case["expected_relation"]["target_relation"]
        )
        for case in cases
    )
    if gold_counts != {"current": 16, "other": 6, "unknown": 2}:
        raise ValueError("reviewed interpretation denominator differs")
    lines = journal_path.read_text(encoding="utf-8").splitlines()
    if len(lines) != 49:
        raise ValueError("oracle journal row count differs")
    rows = [json.loads(line) for line in lines]
    if rows[0] != {
        "event": "header",
        "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
    }:
        raise ValueError("journal header differs")
    per_case = []
    for index, case in enumerate(cases):
        if rows[1 + 2 * index] != {"event": "begin", "case_id": case["id"]}:
            raise ValueError("oracle call order differs")
        end = rows[2 + 2 * index]
        _check_end(end, case)
        per_case.append(
            {
                "id": case["id"],
                "event_status": case["expected_relation"]["event_status"],
                "gold_relation": interpretations.get(case["id"], {}).get(
                    "target_relation", case["expected_relation"]["target_relation"]
                ),
                "predicted_relation": end["source_relation"],
                "gold_route": interpretations.get(case["id"], {}).get(
                    "expected_route", case["expected_route"]
                ),
                "predicted_route": end["route"],
                "error_stage": end["error_stage"],
                "error_type": end["error_type"],
                "http_status": end["http_status"],
                "latency_ms": end["latency_ms"],
            }
        )
    summary = {}
    for name, part in (
        ("RE", per_case[:11]),
        ("V", per_case[11:]),
        ("observed", [row for row in per_case if row["event_status"] == "observed"]),
        ("uncertain", [row for row in per_case if row["event_status"] == "uncertain"]),
        (
            "sensitivity_excluding_V03_V04",
            [row for row in per_case if row["id"] not in {"V03", "V04"}],
        ),
        ("all", per_case),
    ):
        summary[name] = {
            "denominator": len(part),
            "relation_correct": sum(
                row["predicted_relation"] == row["gold_relation"] for row in part
            ),
            "route_correct": sum(row["predicted_route"] == row["gold_route"] for row in part),
            "errors": sum(row["error_stage"] is not None for row in part),
            "gold_relation_counts": dict(Counter(row["gold_relation"] for row in part)),
        }
    by_gold_relation = {}
    for relation, denominator in (("current", 16), ("other", 6), ("unknown", 2)):
        part = [row for row in per_case if row["gold_relation"] == relation]
        if len(part) != denominator:
            raise ValueError("gold relation denominator differs")
        by_gold_relation[relation] = {
            "denominator": denominator,
            "correct": sum(row["predicted_relation"] == relation for row in part),
            "errors": sum(row["error_stage"] is not None for row in part),
            "contract_errors": sum(row["error_stage"] == "contract" for row in part),
            "http_errors": sum(row["http_status"] is not None for row in part),
        }
    by_id = {row["id"]: row for row in per_case}
    contrast_pairs = []
    for current_id, other_id in (("V01", "V02"), ("V05", "V06"), ("V07", "V08")):
        current, other = by_id[current_id], by_id[other_id]
        if current["gold_relation"] != "current" or other["gold_relation"] != "other":
            raise ValueError("contrast pair gold differs")
        first_prediction = current["predicted_relation"]
        second_prediction = other["predicted_relation"]
        contrast_pairs.append(
            {
                "case_ids": [current_id, other_id],
                "gold_relations": ["current", "other"],
                "predicted_relations": [first_prediction, second_prediction],
                "prediction_flipped": (
                    first_prediction is not None
                    and second_prediction is not None
                    and first_prediction != second_prediction
                ),
                "expected_flip_recovered": (
                    first_prediction == "current" and second_prediction == "other"
                ),
                "errors": sum(row["error_stage"] is not None for row in (current, other)),
            }
        )
    development_thresholds = {
        "current_min_correct": 15,
        "other_min_correct": 6,
        "unknown_min_correct": 2,
        "max_errors": 0,
        "met": (
            by_gold_relation["current"]["correct"] >= 15
            and by_gold_relation["other"]["correct"] == 6
            and by_gold_relation["unknown"]["correct"] == 2
            and summary["all"]["errors"] == 0
        ),
    }
    return {
        "interpretation_version": "v2_target_review",
        "historical_comparison_allowed": False,
        "summary": summary,
        "by_gold_relation": by_gold_relation,
        "contrast_pairs": contrast_pairs,
        "development_thresholds": development_thresholds,
        "per_case": per_case,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.protocol, args.journal), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
