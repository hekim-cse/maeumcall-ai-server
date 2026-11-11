"""Independently verify the owner-evidence oracle journal and reviewed labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from scripts.probe_as_safety_clause_index import split_clauses
from scripts.verify_as_safety_oracle_relation_diagnostic import (
    _active_cases,
    _check_spans,
    _route,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
SOURCES = {
    "runner_sha256": ROOT / "scripts/run_as_safety_owner_evidence_diagnostic.py",
    "candidate_sha256": ROOT / "scripts/probe_as_safety_owner_evidence.py",
    "result_verifier_sha256": Path(__file__),
    "oracle_runner_sha256": ROOT / "scripts/run_as_safety_oracle_relation_diagnostic.py",
    "oracle_verifier_sha256": ROOT / "scripts/verify_as_safety_oracle_relation_diagnostic.py",
    "oracle_candidate_sha256": ROOT / "scripts/probe_as_safety_oracle_relation.py",
    "completion_sha256": ROOT / "scripts/as_safety_completion_v2.py",
    "policy_loader_sha256": ROOT / "scripts/run_as_safety_compact_relation_development.py",
    "completion_type_sha256": ROOT / "scripts/as_safety_pair_executor_v2.py",
    "endpoint_guard_sha256": ROOT / "scripts/run_ai_heldout_pair.py",
    "request_policy_type_sha256": ROOT / "evals/structured_nlu/ai_heldout.py",
    "container_check_sha256": ROOT / "scripts/run_as_safety_event_gate_fresh.py",
    "case_loader_sha256": ROOT / "scripts/probe_as_safety_clause_index.py",
    "re_dataset_sha256": DATA / "as-safety-relation-fresh-reviewed.v1.json",
    "v_dataset_sha256": DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
    "spans_sha256": DATA / "as-safety-oracle-relation-spans-reviewed.v1.json",
    "owner_labels_sha256": DATA / "as-safety-owner-evidence-reviewed.v1.json",
    "policy_sha256": DATA / "as-safety-grounded-development-request.v1.json",
}
ACTIVE_IDS = tuple(
    [*(f"RE{i:02}" for i in range(1, 12))]
    + [*(f"V{i:02}" for i in range(1, 11)), "V12", "V14", "V16"]
)
LINK_RELATION = {
    "same_entity": "current",
    "part_or_anaphora": "current",
    "explicit_other": "other",
    "unresolved": "unknown",
}
END_FIELDS = {
    "event",
    "case_id",
    "source_clause_index",
    "source_start",
    "source_end",
    "link_kind",
    "source_relation",
    "route",
    "error_stage",
    "error_type",
    "http_status",
    "finish_reason",
    "latency_ms",
}


def digest(path: Path) -> str:
    """Hash a source file independently of the experiment runner."""
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _reviewed_labels(cases: list[dict], interpretations: dict[str, dict]) -> list[dict]:
    """Independently validate all 24 owner-span and link-kind gold records."""
    payload = json.loads(SOURCES["owner_labels_sha256"].read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or set(payload) != {"kind", "provenance", "review_status", "cases"}
        or payload["kind"] != "as_safety_owner_evidence_reviewed_v1"
        or payload["provenance"] != "ai_authored"
        or payload["review_status"] != "owner_approved_for_exploration"
        or not isinstance(payload["cases"], list)
        or len(payload["cases"]) != 24
    ):
        raise ValueError("reviewed owner label file differs")
    labels = payload["cases"]
    for case, label in zip(cases, labels, strict=True):
        if (
            not isinstance(label, dict)
            or set(label) != {"id", "accepted_owner_spans", "accepted_link_kinds"}
            or label["id"] != case["id"]
        ):
            raise ValueError("owner label order or fields differ")
        gold_relation = interpretations.get(case["id"], {}).get(
            "target_relation", case["expected_relation"]["target_relation"]
        )
        kinds = label["accepted_link_kinds"]
        allowed_kinds = {
            "current": {"same_entity", "part_or_anaphora"},
            "other": {"explicit_other"},
            "unknown": {"unresolved"},
        }[gold_relation]
        if (
            not isinstance(kinds, list)
            or not kinds
            or not all(isinstance(kind, str) for kind in kinds)
            or len(set(kinds)) != len(kinds)
            or not set(kinds) <= allowed_kinds
        ):
            raise ValueError("reviewed owner link kinds differ")
        spans = label["accepted_owner_spans"]
        if not isinstance(spans, list) or bool(spans) == (gold_relation == "unknown"):
            raise ValueError("reviewed owner span nullability differs")
        clauses = split_clauses(case["user_message"])
        accepted = set()
        for span in spans:
            if not isinstance(span, dict) or set(span) != {"clause_index", "mention"}:
                raise ValueError("reviewed owner span fields differ")
            index, mention = span["clause_index"], span["mention"]
            if (
                type(index) is not int
                or not 1 <= index <= len(clauses)
                or not isinstance(mention, str)
                or not mention.strip()
                or clauses[index - 1].count(mention) != 1
                or (index, mention) in accepted
            ):
                raise ValueError("reviewed owner span is not uniquely anchored")
            accepted.add((index, mention))
    return labels


def _check_end(row: dict, case: dict) -> tuple[int | None, str | None]:
    """Verify bounded metadata, reconstruct the quote, and reject raw text."""
    if (
        not isinstance(row, dict)
        or set(row) != END_FIELDS
        or row["event"] != "end"
        or row["case_id"] != case["id"]
    ):
        raise ValueError("owner evidence end row differs")
    latency = row["latency_ms"]
    if type(latency) not in {int, float} or not 0 <= latency < 86_400_000:
        raise ValueError("owner evidence latency differs")
    if row["finish_reason"] not in {None, "stop", "length"}:
        raise ValueError("owner evidence finish reason differs")
    status = row["http_status"]
    if status is not None and (type(status) is not int or not 100 <= status <= 599):
        raise ValueError("owner evidence HTTP status differs")
    if row["error_stage"] is None:
        if (
            row["error_type"] is not None
            or status is not None
            or row["finish_reason"] != "stop"
            or row["link_kind"] not in LINK_RELATION
            or row["source_relation"] != LINK_RELATION[row["link_kind"]]
            or row["route"]
            != _route(row["source_relation"], case["expected_relation"]["event_status"])
        ):
            raise ValueError("successful owner evidence decision differs")
        index, start, end = (row["source_clause_index"], row["source_start"], row["source_end"])
        if row["link_kind"] == "unresolved":
            if (index, start, end) != (None, None, None):
                raise ValueError("unresolved evidence must have null offsets")
            return None, None
        clauses = split_clauses(case["user_message"])
        if (
            type(index) is not int
            or not 1 <= index <= len(clauses)
            or type(start) is not int
            or type(end) is not int
            or not 0 <= start < end <= len(clauses[index - 1])
        ):
            raise ValueError("owner evidence offsets differ")
        mention = clauses[index - 1][start:end]
        if not mention.strip() or clauses[index - 1].count(mention) != 1:
            raise ValueError("owner evidence offset is ambiguous")
        return index, mention
    if row["error_stage"] not in {"response", "contract"} or (
        not isinstance(row["error_type"], str)
        or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", row["error_type"])
    ):
        raise ValueError("owner evidence error metadata differs")
    if any(
        row[name] is not None
        for name in (
            "source_clause_index",
            "source_start",
            "source_end",
            "link_kind",
            "source_relation",
            "route",
        )
    ):
        raise ValueError("failed owner evidence response has decision data")
    if row["error_stage"] == "contract" and (row["finish_reason"] != "stop" or status is not None):
        raise ValueError("owner evidence contract error metadata differs")
    if status is not None and row["error_stage"] != "response":
        raise ValueError("owner evidence HTTP error stage differs")
    return None, None


def verify(protocol_path: Path, journal_path: Path) -> dict:
    """Recompute every denominator, citation offset, relation, and route."""
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    if (
        protocol.get("kind") != "as_safety_owner_evidence_diagnostic_v1"
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
        raise ValueError("owner evidence protocol differs")
    for key, path in SOURCES.items():
        if digest(path) != protocol.get(key):
            raise ValueError(f"frozen {key} differs")
    cases = _active_cases()
    if tuple(case["id"] for case in cases) != ACTIVE_IDS:
        raise ValueError("owner evidence active order differs")
    interpretations = _check_spans(cases)
    labels = _reviewed_labels(cases, interpretations)
    gold_counts = Counter(
        interpretations.get(case["id"], {}).get(
            "target_relation", case["expected_relation"]["target_relation"]
        )
        for case in cases
    )
    if gold_counts != {"current": 16, "other": 6, "unknown": 2}:
        raise ValueError("owner evidence gold denominator differs")
    lines = journal_path.read_text(encoding="utf-8").splitlines()
    if len(lines) != 49:
        raise ValueError("owner evidence journal row count differs")
    rows = [json.loads(line) for line in lines]
    if rows[0] != {
        "event": "header",
        "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
    }:
        raise ValueError("owner evidence journal header differs")
    per_case = []
    for index, (case, label) in enumerate(zip(cases, labels, strict=True)):
        if rows[1 + 2 * index] != {"event": "begin", "case_id": case["id"]}:
            raise ValueError("owner evidence call order differs")
        end = rows[2 + 2 * index]
        source_index, source_mention = _check_end(end, case)
        relation = interpretations.get(case["id"], {}).get(
            "target_relation", case["expected_relation"]["target_relation"]
        )
        route = interpretations.get(case["id"], {}).get("expected_route", case["expected_route"])
        accepted = {
            (span["clause_index"], span["mention"]) for span in label["accepted_owner_spans"]
        }
        source_correct = (
            (source_index is None and not accepted) if end["error_stage"] is None else False
        ) or (end["error_stage"] is None and (source_index, source_mention) in accepted)
        link_correct = (
            end["error_stage"] is None and end["link_kind"] in label["accepted_link_kinds"]
        )
        per_case.append(
            {
                "id": case["id"],
                "event_status": case["expected_relation"]["event_status"],
                "gold_relation": relation,
                "predicted_relation": end["source_relation"],
                "gold_route": route,
                "predicted_route": end["route"],
                "predicted_link_kind": end["link_kind"],
                "source_span_correct": source_correct,
                "link_kind_correct": link_correct,
                "source_clause_index": end["source_clause_index"],
                "source_start": end["source_start"],
                "source_end": end["source_end"],
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
            "source_span_correct": sum(row["source_span_correct"] for row in part),
            "link_kind_correct": sum(row["link_kind_correct"] for row in part),
            "evidence_and_relation_correct": sum(
                row["source_span_correct"]
                and row["link_kind_correct"]
                and row["predicted_relation"] == row["gold_relation"]
                for row in part
            ),
            "errors": sum(row["error_stage"] is not None for row in part),
            "gold_relation_counts": dict(Counter(row["gold_relation"] for row in part)),
        }
    by_gold_relation = {}
    for relation, denominator in (("current", 16), ("other", 6), ("unknown", 2)):
        part = [row for row in per_case if row["gold_relation"] == relation]
        if len(part) != denominator:
            raise ValueError("owner evidence relation denominator differs")
        by_gold_relation[relation] = {
            "denominator": denominator,
            "correct": sum(row["predicted_relation"] == relation for row in part),
            "errors": sum(row["error_stage"] is not None for row in part),
        }
    by_id = {row["id"]: row for row in per_case}
    contrast_pairs = []
    for current_id, other_id in (("V01", "V02"), ("V05", "V06"), ("V07", "V08")):
        current, other = by_id[current_id], by_id[other_id]
        if current["gold_relation"] != "current" or other["gold_relation"] != "other":
            raise ValueError("owner evidence contrast gold differs")
        contrast_pairs.append(
            {
                "case_ids": [current_id, other_id],
                "predicted_relations": [current["predicted_relation"], other["predicted_relation"]],
                "expected_flip_recovered": (
                    current["predicted_relation"] == "current"
                    and other["predicted_relation"] == "other"
                ),
                "errors": sum(row["error_stage"] is not None for row in (current, other)),
            }
        )
    thresholds = {
        "current_min_correct": 15,
        "other_min_correct": 6,
        "unknown_min_correct": 2,
        "max_errors": 0,
        "contrast_pairs_min_correct": 3,
        "met": (
            by_gold_relation["current"]["correct"] >= 15
            and by_gold_relation["other"]["correct"] == 6
            and by_gold_relation["unknown"]["correct"] == 2
            and summary["all"]["errors"] == 0
            and all(pair["expected_flip_recovered"] for pair in contrast_pairs)
        ),
    }
    return {
        "interpretation_version": "v2_target_review",
        "historical_comparison_allowed": False,
        "summary": summary,
        "by_gold_relation": by_gold_relation,
        "contrast_pairs": contrast_pairs,
        "development_thresholds": thresholds,
        "per_case": per_case,
    }


def main() -> None:
    """Read a frozen protocol and journal for a read-only independent audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.protocol, args.journal), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
