"""Compare source-only morphological span filters on exposed development data.

This measures candidate availability, not owner selection, abstention, or
model accuracy. Only source text is passed to candidate generation; reviewed
spans are used to score the generated candidates.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import kiwipiepy
from kiwipiepy import Kiwi

from experiments.as_safety_v2.quotes import split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate, generate_source_lattice

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
SOURCES = {
    "PC_NC": DATA / "as-safety-eb-controls-v5-cases.json",
    "RE": DATA / "as-safety-relation-fresh-reviewed.v1.json",
    "V": DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
}
LABELS = DATA / "as-safety-owner-evidence-reviewed.v1.json"
SOURCE_SHA256 = {
    "PC_NC": "11d76e8c047241dd8898733fd4334309095d965527878a41c222bc779849036d",
    "RE": "b601d000ee4a8b8ffee114179099283f1d75f9226514cfd31467f99993f158cd",
    "V": "cf07b01f1107d3fc15b232ff85692188d2a807fc425865768163f4d4fb12bf5e",
}
LABEL_SHA256 = "785b2cab6c4cf4cc3ed545676ed27f1b39ce09c24ff0465e963f298aecb15f56"
KIWI_VERSION = "0.23.2"
FILTERS = ("baseline", "nominal_end", "nominal_chunk")
_NOMINAL_TAGS = {"NP", "NR", "SL", "SH", "SN", "XSN"}
_CHUNK_TAGS = _NOMINAL_TAGS | {"MM", "JKG"}


def _nominal(tag: str) -> bool:
    return tag.startswith("NN") or tag in _NOMINAL_TAGS


def candidate_views(message: str, kiwi: Kiwi) -> dict[str, tuple[SourceCandidate, ...]]:
    """Return subsets of the unchanged source lattice, using source text only.

    A nominal end removes trailing particles or predicates. The stricter
    contiguous chunk also excludes internal case particles and predicates.
    This deliberately makes no claim that a surviving noun is a hazard owner.
    """
    lattice = generate_source_lattice(message, max_window_tokens=5, max_candidates=192)
    clauses = split_clauses(message)
    tokens_by_clause = tuple(tuple(kiwi.tokenize(clause)) for clause in clauses)
    end_by_clause = tuple(
        {token.start + token.len for token in tokens if _nominal(token.tag)}
        for tokens in tokens_by_clause
    )
    end_candidates = tuple(
        candidate
        for candidate in lattice.candidates
        if candidate.end in end_by_clause[candidate.clause_index - 1]
    )

    def is_chunk(candidate: SourceCandidate) -> bool:
        tokens = tokens_by_clause[candidate.clause_index - 1]
        intersecting = tuple(
            token
            for token in tokens
            if token.start < candidate.end and token.start + token.len > candidate.start
        )
        return bool(intersecting) and all(
            candidate.start <= token.start
            and token.start + token.len <= candidate.end
            and (_nominal(token.tag) or token.tag in _CHUNK_TAGS)
            for token in intersecting
        )

    return {
        "baseline": lattice.candidates,
        "nominal_end": end_candidates,
        "nominal_chunk": tuple(candidate for candidate in end_candidates if is_chunk(candidate)),
    }


def _read_json(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    payload = json.loads(raw)
    if type(payload) is not dict or type(payload.get("cases")) is not list:
        raise ValueError(f"invalid development input: {path.name}")
    return payload, hashlib.sha256(raw).hexdigest()


def _source_cases() -> tuple[dict[str, str], dict[str, str]]:
    sources: dict[str, str] = {}
    digests = {}
    for name, path in SOURCES.items():
        payload, digests[name] = _read_json(path)
        if digests[name] != SOURCE_SHA256[name]:
            raise ValueError(f"development source digest differs: {name}")
        for case in payload["cases"]:
            case_id = case.get("case_id") if name == "PC_NC" else case.get("id")
            message = case.get("user_message")
            if (
                type(case_id) is not str
                or type(message) is not str
                or not message.strip()
                or case_id in sources
            ):
                raise ValueError("duplicate or invalid development source")
            sources[case_id] = message
    return sources, digests


def _gold_labels(source_ids: set[str]) -> tuple[dict[str, list[tuple[int, str]]], str]:
    pc_payload, pc_digest = _read_json(SOURCES["PC_NC"])
    if pc_digest != SOURCE_SHA256["PC_NC"]:
        raise ValueError("control source digest changed")
    reviewed, digest = _read_json(LABELS)
    if digest != LABEL_SHA256:
        raise ValueError("reviewed owner digest differs")
    labels: dict[str, list[tuple[int, str]]] = {}
    for case in pc_payload["cases"]:
        gold = case["gold_subject_span"]
        labels[case["case_id"]] = [] if gold is None else [(gold["clause_index"], gold["quote"])]
    for case in reviewed["cases"]:
        case_id = case["id"]
        if case_id in labels:
            raise ValueError("duplicate gold case")
        labels[case_id] = [
            (span["clause_index"], span["mention"]) for span in case["accepted_owner_spans"]
        ]
    if not set(labels).issubset(source_ids):
        raise ValueError("gold case lacks a source")
    return labels, digest


def audit() -> dict:
    """Compute descriptive candidate coverage; never use labels to filter."""
    if kiwipiepy.__version__ != KIWI_VERSION:
        raise ValueError("Kiwi version differs")
    sources, source_digests = _source_cases()
    kiwi = Kiwi()
    candidates = {case_id: candidate_views(message, kiwi) for case_id, message in sources.items()}
    labels, label_digest = _gold_labels(set(sources))
    summary = {
        "case_count": len(labels),
        "positive_case_count": 0,
        "null_case_count": 0,
        "candidate_count_by_filter": {name: 0 for name in FILTERS},
        "positive_gold_covered_by_filter": {name: 0 for name in FILTERS},
        "additional_gold_loss_vs_baseline_by_filter": {name: 0 for name in FILTERS},
        "additional_gold_loss_case_ids_by_filter": {name: [] for name in FILTERS},
        "positive_gold_total": 0,
    }
    rows = []
    for case_id in sorted(labels):
        message = sources[case_id]
        clauses = split_clauses(message)
        gold = labels[case_id]
        for index, quote in gold:
            if (
                type(index) is not int
                or not 1 <= index <= len(clauses)
                or type(quote) is not str
                or not quote.strip()
                or clauses[index - 1].count(quote) != 1
            ):
                raise ValueError(f"unanchored or ambiguous gold: {case_id}")
        row = {"case_id": case_id, "gold_required": bool(gold), "gold_span_count": len(gold)}
        if gold:
            summary["positive_case_count"] += 1
            summary["positive_gold_total"] += len(gold)
        else:
            summary["null_case_count"] += 1
        row["candidate_count_by_filter"] = {}
        row["gold_covered_by_filter"] = {}
        row["gold_candidate_ids_by_filter"] = {}
        for name, view in candidates[case_id].items():
            count = len(view)
            ids_by_span = [
                [item.id for item in view if (item.clause_index, item.quote) == span]
                for span in gold
            ]
            if any(len(ids) > 1 for ids in ids_by_span):
                raise ValueError(f"ambiguous gold candidate: {case_id}")
            covered = sum(bool(ids) for ids in ids_by_span)
            row["candidate_count_by_filter"][name] = count
            row["gold_covered_by_filter"][name] = covered if gold else None
            row["gold_candidate_ids_by_filter"][name] = (
                [ids[0] for ids in ids_by_span if ids] if gold else None
            )
            summary["candidate_count_by_filter"][name] += count
            summary["positive_gold_covered_by_filter"][name] += covered
        baseline_covered = row["gold_covered_by_filter"]["baseline"] or 0
        row["additional_gold_loss_vs_baseline_by_filter"] = {}
        for name in FILTERS:
            lost = baseline_covered - (row["gold_covered_by_filter"][name] or 0)
            if lost < 0:
                raise ValueError("filter is not a subset of baseline")
            row["additional_gold_loss_vs_baseline_by_filter"][name] = lost
            summary["additional_gold_loss_vs_baseline_by_filter"][name] += lost
            if lost:
                summary["additional_gold_loss_case_ids_by_filter"][name].append(case_id)
        rows.append(row)
    return {
        "kind": "as_safety_eb_boundary_v8_exposed_offline_audit",
        "scope": "PC_NC_RE_V_exposed_development_only",
        "model_called": False,
        "owner_selection_or_abstention_evaluated": False,
        "kiwipiepy_version": KIWI_VERSION,
        "source_sha256_by_group": source_digests,
        "reviewed_owner_sha256": label_digest,
        "summary": summary,
        "cases": rows,
    }


def main() -> None:
    print(json.dumps(audit(), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
