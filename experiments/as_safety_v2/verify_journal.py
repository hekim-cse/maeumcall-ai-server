"""Independent source-span, journal-transition and metric checks."""

from __future__ import annotations

import math
from pathlib import Path

from experiments.as_safety_v2.verify_sources import (
    CASE_IDS,
    ERROR_RE,
    OWNER_KINDS,
    RELATIONS,
    SHA_RE,
    STAGE1_KEYS,
    STAGE2_KEYS,
    ContractError,
    _json,
    _span,
    digest,
)

TRANSPORT_ERRORS = {
    "request_too_large",
    "redirect",
    "http_status",
    "http_error",
    "network_error",
    "timeout",
    "response_too_large",
    "invalid_response_json",
    "response_fields_invalid",
}


def _response_error(stage: dict) -> None:
    if stage["error_field"] is not None:
        raise ValueError("response failure has error field")
    if stage["error_code"] == "finish_length":
        if stage["finish_reason"] != "length" or stage["raw_sha256"] is None:
            raise ValueError("length failure metadata differs")
    elif stage["error_code"] in TRANSPORT_ERRORS:
        if stage["finish_reason"] is not None or stage["raw_sha256"] is not None:
            raise ValueError("transport failure metadata differs")
    else:
        raise ValueError("response failure code differs")


def _raw_meta(stage: dict, private_dir: Path | None, case_id: str, number: int) -> str | None:
    sha, size = stage["raw_sha256"], stage["raw_bytes"]
    if sha is None:
        if size is not None:
            raise ValueError("raw metadata differs")
        return None
    if (
        type(sha) is not str
        or not SHA_RE.fullmatch(sha)
        or type(size) is not int
        or not 0 <= size <= 1_000_000
    ):
        raise ValueError("raw metadata differs")
    if private_dir is None:
        return None
    raw = (private_dir / f"{case_id}-stage{number}.json.txt").read_bytes()
    if len(raw) != size or digest(raw) != sha:
        raise ValueError("private raw artifact differs")
    return raw.decode("utf-8")


def _raw_span(item: object, clauses: tuple[str, ...], field: str) -> dict | None:
    if item is None:
        return None
    if type(item) is not dict or set(item) != {"clause_index", "quote"}:
        raise ContractError("quote_fields_invalid", field)
    index, quote = item["clause_index"], item["quote"]
    if type(index) is not int or not 1 <= index <= len(clauses):
        raise ContractError("quote_index_invalid", field)
    if type(quote) is not str:
        raise ContractError("quote_type_invalid", field)
    if not quote.strip() or quote != quote.strip():
        raise ContractError("quote_blank", field)
    start = clauses[index - 1].find(quote)
    if start < 0:
        raise ContractError("quote_unanchored", field)
    if clauses[index - 1].find(quote, start + 1) >= 0:
        raise ContractError("quote_nonunique", field)
    return {
        "clause_index": index,
        "start": start,
        "end": start + len(quote),
        "quote_sha256": digest(quote.encode("utf-8")),
    }


def _raw_stage1(raw: str, clauses: tuple[str, ...]) -> tuple[dict, str]:
    parsed = _json(raw)
    if type(parsed) is not dict or set(parsed) != {
        "event_span",
        "subject_span",
        "owner_span",
        "owner_kind",
    }:
        raise ContractError("fields_invalid", "stage1")
    kind = parsed["owner_kind"]
    if type(kind) is not str or kind not in OWNER_KINDS:
        raise ContractError("owner_kind_invalid", "owner_kind")
    spans = {
        name: _raw_span(parsed[name], clauses, name)
        for name in ("event_span", "subject_span", "owner_span")
    }
    if (spans["owner_span"] is None) != (kind == "unresolved"):
        raise ContractError("owner_consistency_invalid", "owner_span")
    return spans, kind


def _raw_stage2(
    raw: str, clauses: tuple[str, ...], owner_kind: str
) -> tuple[str, str, dict | None]:
    parsed = _json(raw)
    if type(parsed) is not dict or set(parsed) != {"source_relation", "distinct_evidence_span"}:
        raise ContractError("fields_invalid", "stage2")
    relation = parsed["source_relation"]
    if type(relation) is not str or relation not in RELATIONS:
        raise ContractError("relation_invalid", "source_relation")
    cue = _raw_span(parsed["distinct_evidence_span"], clauses, "distinct_evidence_span")
    if relation != "other" and cue is not None:
        raise ContractError("distinct_evidence_inconsistent", "distinct_evidence_span")
    effective = (
        "unknown" if relation == "other" and (cue is None or owner_kind != "explicit") else relation
    )
    return relation, effective, cue


def _number(value: object, *, nullable: bool = False) -> bool:
    return (value is None and nullable) or (
        type(value) in {int, float} and math.isfinite(value) and 0 <= value < 86_400_000
    )


def _route(relation: str, event_status: str) -> str:
    if relation == "other":
        return "collecting_service_request"
    if relation == "current" and event_status == "observed":
        return "safety_action_required"
    return "confirming_safety_status"


def _check_stage1(stage: object, case: dict, private_dir: Path | None) -> None:
    if type(stage) is not dict or set(stage) != STAGE1_KEYS or stage["called"] is not True:
        raise ValueError("stage1 fields differ")
    status = stage["status"]
    if status not in {"validated", "contract_error", "response_error"} or not _number(
        stage["latency_ms"]
    ):
        raise ValueError("stage1 status or latency differs")
    raw = _raw_meta(stage, private_dir, case["id"], 1)
    if stage["finish_reason"] not in {None, "stop", "length"}:
        raise ValueError("stage1 finish reason differs")
    if status == "validated":
        if (
            stage["finish_reason"] != "stop"
            or stage["raw_sha256"] is None
            or stage["error_code"] is not None
            or stage["error_field"] is not None
        ):
            raise ValueError("validated stage1 metadata differs")
        spans = stage["spans"]
        if type(spans) is not dict or set(spans) != {"event_span", "subject_span", "owner_span"}:
            raise ValueError("stage1 spans differ")
        for value in spans.values():
            _span(value, case["clauses"])
        if stage["owner_kind"] not in OWNER_KINDS or (
            (spans["owner_span"] is None) != (stage["owner_kind"] == "unresolved")
        ):
            raise ValueError("stage1 owner kind differs")
        if raw is not None and (spans, stage["owner_kind"]) != _raw_stage1(raw, case["clauses"]):
            raise ValueError("stage1 raw decision differs")
    else:
        if stage["spans"] is not None or stage["owner_kind"] is not None:
            raise ValueError("failed stage1 has accepted spans")
        if type(stage["error_code"]) is not str or not ERROR_RE.fullmatch(stage["error_code"]):
            raise ValueError("stage1 failure code differs")
        if status == "contract_error":
            if (
                type(stage["error_field"]) is not str
                or not stage["error_field"]
                or len(stage["error_field"]) > 64
                or stage["finish_reason"] != "stop"
                or stage["raw_sha256"] is None
            ):
                raise ValueError("stage1 contract failure lacks raw response")
            if raw is not None:
                try:
                    _raw_stage1(raw, case["clauses"])
                except ContractError as error:
                    if (error.code, error.field) != (stage["error_code"], stage["error_field"]):
                        raise ValueError("stage1 raw error code differs") from error
                else:
                    raise ValueError("stage1 raw unexpectedly valid")
        else:
            _response_error(stage)


def _check_stage2(stage: object, first: dict, case: dict, private_dir: Path | None) -> None:
    if type(stage) is not dict or set(stage) != STAGE2_KEYS:
        raise ValueError("stage2 fields differ")
    called = first["status"] == "validated" and all(
        first["spans"][key] is not None for key in ("event_span", "subject_span", "owner_span")
    )
    if stage["called"] is not called:
        raise ValueError("stage2 call transition differs")
    if not called:
        expected_reason = (
            "stage1_invalid" if first["status"] != "validated" else "missing_event_subject_owner"
        )
        if stage != {
            "called": False,
            "status": "skipped",
            "skip_reason": expected_reason,
            **{key: None for key in STAGE2_KEYS - {"called", "status", "skip_reason"}},
        }:
            raise ValueError("stage2 skip state differs")
        return
    if (
        stage["status"] not in {"validated", "contract_error", "response_error"}
        or stage["skip_reason"] is not None
        or not _number(stage["latency_ms"])
    ):
        raise ValueError("stage2 status differs")
    raw = _raw_meta(stage, private_dir, case["id"], 2)
    if stage["finish_reason"] not in {None, "stop", "length"}:
        raise ValueError("stage2 finish reason differs")
    if stage["status"] == "validated":
        if (
            stage["finish_reason"] != "stop"
            or stage["raw_sha256"] is None
            or stage["error_code"] is not None
            or stage["error_field"] is not None
        ):
            raise ValueError("validated stage2 metadata differs")
        model, effective = stage["model_relation"], stage["effective_relation"]
        if model not in RELATIONS or effective not in RELATIONS:
            raise ValueError("stage2 relation differs")
        evidence = _span(stage["distinct_evidence_span"], case["clauses"])
        if model != "other" and evidence is not None:
            raise ValueError("stage2 evidence inconsistent")
        expected = (
            "unknown"
            if model == "other" and (first["owner_kind"] != "explicit" or evidence is None)
            else model
        )
        if effective != expected:
            raise ValueError("stage2 effective relation differs")
        if raw is not None:
            if _raw_stage2(raw, case["clauses"], first["owner_kind"]) != (
                model,
                effective,
                evidence,
            ):
                raise ValueError("stage2 raw decision differs")
    else:
        if any(
            stage[key] is not None
            for key in ("model_relation", "effective_relation", "distinct_evidence_span")
        ):
            raise ValueError("failed stage2 has accepted decision")
        if type(stage["error_code"]) is not str or not ERROR_RE.fullmatch(stage["error_code"]):
            raise ValueError("stage2 failure code differs")
        if stage["status"] == "contract_error":
            if (
                type(stage["error_field"]) is not str
                or not stage["error_field"]
                or len(stage["error_field"]) > 64
                or stage["finish_reason"] != "stop"
                or stage["raw_sha256"] is None
            ):
                raise ValueError("stage2 contract failure lacks raw response")
            if raw is not None:
                try:
                    _raw_stage2(raw, case["clauses"], first["owner_kind"])
                except ContractError as error:
                    if (error.code, error.field) != (stage["error_code"], stage["error_field"]):
                        raise ValueError("stage2 raw error code differs") from error
                else:
                    raise ValueError("stage2 raw unexpectedly valid")
        else:
            _response_error(stage)


def check_end(row: object, case: dict, private_dir: Path | None = None) -> dict:
    if (
        type(row) is not dict
        or set(row)
        != {"event", "case_id", "stage1", "stage2", "source_relation", "route", "total_latency_ms"}
        or row["event"] != "end"
        or row["case_id"] != case["id"]
    ):
        raise ValueError("journal end row differs")
    first, second = row["stage1"], row["stage2"]
    _check_stage1(first, case, private_dir)
    _check_stage2(second, first, case, private_dir)
    relation = second["effective_relation"] if second["status"] == "validated" else "unknown"
    if row["source_relation"] != relation or row["route"] != _route(relation, case["event_status"]):
        raise ValueError("final relation or route differs")
    if not _number(row["total_latency_ms"]) or row["total_latency_ms"] + 0.01 < first[
        "latency_ms"
    ] + (second["latency_ms"] or 0):
        raise ValueError("total latency differs")
    spans = first["spans"] if first["status"] == "validated" else None
    matches = {
        name: spans is not None and spans[f"{name}_span"] == case["references"][f"{name}_reference"]
        for name in ("event", "subject", "owner")
    }
    return {
        "id": case["id"],
        "gold_relation": case["relation"],
        "event_status": case["event_status"],
        "predicted_relation": relation,
        "predicted_route": row["route"],
        "gold_route": _route(case["relation"], case["event_status"]),
        "error": first["status"] != "validated"
        or second["status"] in {"contract_error", "response_error"},
        "stage1_valid": first["status"] == "validated",
        "stage2_called": second["called"],
        "calls": 1 + int(second["called"]),
        "reference_matches": matches,
        "stage1_latency_ms": first["latency_ms"],
        "stage2_latency_ms": second["latency_ms"],
        "total_latency_ms": row["total_latency_ms"],
    }


def _aggregate(rows: list[dict]) -> dict:
    return {
        "denominator": len(rows),
        "relation_correct": sum(r["predicted_relation"] == r["gold_relation"] for r in rows),
        "route_correct": sum(r["predicted_route"] == r["gold_route"] for r in rows),
        "errors": sum(r["error"] for r in rows),
        "stage1_contract_pass": sum(r["stage1_valid"] for r in rows),
        "stage2_called": sum(r["stage2_called"] for r in rows),
        "calls": sum(r["calls"] for r in rows),
        "exact_reference_matches": {
            name: sum(r["reference_matches"][name] for r in rows)
            for name in ("event", "subject", "owner")
        },
    }


def _percentile(values: list[float], percent: int) -> float | None:
    if not values:
        return None
    return sorted(values)[(percent * len(values) + 99) // 100 - 1]


def summarize(rows: list[dict]) -> dict:
    if tuple(row["id"] for row in rows) != CASE_IDS:
        raise ValueError("summary case order differs")
    by_id = {row["id"]: row for row in rows}
    pairs = [("V01", "V02"), ("V05", "V06"), ("V07", "V08")]
    contrast = [
        {
            "case_ids": list(pair),
            "recovered": [by_id[case_id]["predicted_relation"] for case_id in pair]
            == ["current", "other"]
            and not any(by_id[case_id]["error"] for case_id in pair),
        }
        for pair in pairs
    ]
    all_group = _aggregate(rows)
    current = _aggregate([r for r in rows if r["gold_relation"] == "current"])
    other = _aggregate([r for r in rows if r["gold_relation"] == "other"])
    current_observed = _aggregate(
        [r for r in rows if r["gold_relation"] == "current" and r["event_status"] == "observed"]
    )
    gate = {
        "current_min_correct": 15,
        "current_observed_min_correct": 13,
        "other_min_correct": 6,
        "max_errors": 0,
        "contrast_min_recovered": 3,
    }
    gate["met"] = (
        current["relation_correct"] >= 15
        and current_observed["relation_correct"] == 13
        and other["relation_correct"] == 6
        and all_group["errors"] == 0
        and sum(pair["recovered"] for pair in contrast) == 3
    )
    return {
        "all": all_group,
        "current": current,
        "other": other,
        "current_observed": current_observed,
        "stage2_called": _aggregate([r for r in rows if r["stage2_called"]]),
        "contrast_pairs": contrast,
        "development_gate": gate,
        "latency_nearest_rank_ms": {
            key: {
                "denominator": len(values),
                "p50": _percentile(values, 50),
                "p95": _percentile(values, 95),
            }
            for key, values in {
                "total": [r["total_latency_ms"] for r in rows],
                "stage1": [r["stage1_latency_ms"] for r in rows],
                "stage2_called": [r["stage2_latency_ms"] for r in rows if r["stage2_called"]],
            }.items()
        },
    }
