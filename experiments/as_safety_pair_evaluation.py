"""Shared offline comparison of source detectors on annotated candidate pairs."""

import hashlib
import json
from collections.abc import Callable, Mapping
from importlib.metadata import version
from pathlib import Path

from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_explicit_source import DirectSource
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate

Detector = Callable[[FixedPair, str, Kiwi], DirectSource | None]


def predict(detector: Detector, pair: FixedPair, occurrence: str, kiwi: Kiwi) -> str:
    try:
        return "approve" if detector(pair, occurrence, kiwi) is not None else "abstain"
    except (ValidationError, ValueError):
        return "error"


def summarize(rows: list[dict], name: str) -> dict:
    positive = [row for row in rows if row["gold"] == "approve"]
    negative = [row for row in rows if row["gold"] == "abstain"]
    pairs: dict[str, list[bool]] = {}
    for row in rows:
        pairs.setdefault(row["case"], []).append(row[name] == row["gold"])
    return {
        "positive_total": len(positive),
        "negative_total": len(negative),
        "true_approval": sum(row[name] == "approve" for row in positive),
        "missed_approval": sum(row[name] == "abstain" for row in positive),
        "false_approval": sum(row[name] == "approve" for row in negative),
        "correct_abstention": sum(row[name] == "abstain" for row in negative),
        "errors": sum(row[name] == "error" for row in rows),
        "pairs_total": len(pairs),
        "pairs_passed": sum(all(pair) for pair in pairs.values()),
    }


def compare(path: Path, kind: str, detectors: Mapping[str, Detector]) -> dict:
    raw = path.read_bytes()
    fixture = json.loads(raw)
    if fixture["kind"] != kind:
        raise ValueError("unexpected fixture kind")
    kiwi = Kiwi()
    rows = []
    seen = set()
    for case in fixture["cases"]:
        key = case["id"]
        if key in seen or len(case["candidates"]) != 2:
            raise ValueError(f"invalid or duplicate pair: {key}")
        seen.add(key)
        original = case["utterance"]
        clauses = split_clauses(original)
        event = anchor_span(case["event"], clauses, field="event")
        for index, item in enumerate(case["candidates"], 1):
            identifier = f"{key}-{index}"
            span = anchor_span(item["span"], clauses, field=identifier)
            if (
                event is None
                or span is None
                or item["id"] != identifier
                or type(item["approve"]) is not bool
            ):
                raise ValueError(f"invalid reviewed candidate: {identifier}")
            pair = FixedPair(original, clauses, event, SourceCandidate(identifier, **span))
            outcomes = {
                name: predict(detector, pair, case["occurrence"], kiwi)
                for name, detector in detectors.items()
            }
            rows.append(
                {
                    "case": key,
                    "id": identifier,
                    "quote": pair.candidate.quote,
                    "gold": "approve" if item["approve"] else "abstain",
                    **outcomes,
                }
            )
    return {
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "provenance": fixture["provenance"],
        "kiwipiepy": version("kiwipiepy"),
        "kiwipiepy_model": version("kiwipiepy_model"),
        "summary": {name: summarize(rows, name) for name in detectors},
        "rows": rows,
    }


def compare_with_locations(path: Path, kind: str, detectors: Mapping[str, Detector]) -> dict:
    """Compare decisions and separately score the fixed observation-location subset."""
    frozen = path.read_bytes()
    location_ids = json.loads(frozen)["observation_location_candidates"]
    result = compare(path, kind, detectors)
    if result["input_sha256"] != hashlib.sha256(frozen).hexdigest():
        raise ValueError("reviewed fixture changed during evaluation")
    rows = {row["id"]: row for row in result["rows"]}
    if len(location_ids) != len(set(location_ids)) or any(
        candidate not in rows or rows[candidate]["gold"] != "abstain" for candidate in location_ids
    ):
        raise ValueError("location subset must contain unique abstention labels")
    for name, summary in result["summary"].items():
        summary["location_total"] = len(location_ids)
        summary["location_false_approval"] = sum(
            rows[candidate][name] == "approve" for candidate in location_ids
        )
    return result
