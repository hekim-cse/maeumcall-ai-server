"""Offline, case-level audit of the frozen six-case A/S candidate-ID probe.

This script never calls a model. It reconstructs the source-only candidate list
from the exact committed generator used in the probe, then compares the public
journal with the reviewed references only after generation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import types
from pathlib import Path

from experiments.as_safety_v2.cases import load_development_cases
from experiments.as_safety_v2.quotes import split_clauses
from experiments.as_safety_v2.run import INPUTS, ROOT
from experiments.as_safety_v2.source_lattice import (
    generate_source_lattice,
    source_candidate_status,
)

DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
PROTOCOL = DATA / "as-safety-extraction-v2-probe-protocol.v1.json"
JOURNAL = DATA / "as-safety-extraction-v2-probe-journal.v1.jsonl"
PROTOCOL_SHA256 = "c5cc4020b157f34f578cfc0aa207281c1ec6705c2a4d75e7ce79771bb0f3dcff"
JOURNAL_SHA256 = "06c7ebec369a2cf316fdb818a74e3adc50b5cd0d19c0ea13f27110442666dfdf"
CASE_IDS = ("RE03", "RE06", "RE09", "V01", "V04", "V07")
FIELD_NAMES = (("event_span", "event"), ("subject_span", "subject"), ("owner_span", "owner"))


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _checked_bytes(path: Path, expected: str) -> bytes:
    payload = path.read_bytes()
    if _sha(payload) != expected:
        raise ValueError(f"frozen artifact differs: {path.name}")
    return payload


def _frozen_file(commit: str, relative: str) -> bytes:
    if (
        not re.fullmatch(r"[0-9a-f]{40}", commit)
        or relative.startswith("/")
        or ".." in Path(relative).parts
    ):
        raise ValueError("invalid frozen source identity")
    return subprocess.run(
        ("git", "show", f"{commit}:{relative}"),
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout


def _frozen_generator(protocol: dict):
    relative = "experiments/as_safety_v2/candidate_ids.py"
    source = _frozen_file(protocol["frozen_code_commit"], relative)
    if _sha(source) != protocol["source_manifest"][relative]:
        raise ValueError("frozen generator hash differs")
    # Its generation imports the quote/target helpers; assert those are unchanged
    # from the probe before loading the historical source in a private module.
    # json_contract.py changed only its duplicate-key error field after the
    # probe; generation never parses model JSON, so it cannot affect candidates.
    for dependency in ("quotes.py", "extraction.py", "cases.py"):
        path = f"experiments/as_safety_v2/{dependency}"
        _checked_bytes(ROOT / path, protocol["source_manifest"][path])
    name = "_as_safety_candidate_probe_frozen_generator"
    module = types.ModuleType(name)
    module.__file__ = f"{protocol['frozen_code_commit']}:{relative}"
    sys.modules[name] = module
    try:
        exec(compile(source, module.__file__, "exec"), module.__dict__)
    finally:
        sys.modules.pop(name, None)
    return module.generate_candidates, module.measure_candidate_coverage


def _failure_reason(message: str, span: dict, max_window_tokens: int) -> str:
    clause = split_clauses(message)[span["clause_index"] - 1]
    quote = span["quote"]
    start = clause.index(quote)
    tokens = tuple(re.finditer(r"\S+", clause))
    if len(tuple(re.finditer(r"\S+", quote))) > max_window_tokens:
        return "over_window_limit"
    if not any(token.start() == start for token in tokens):
        return "starts_inside_token"
    end = start + len(quote)
    if not any(token.end() == end for token in tokens):
        return "unsupported_final_suffix_or_internal_end"
    return "other_generation_gap"


def _load_journal(path: Path, protocol_sha: str, order: list[dict]) -> list[dict]:
    lines = _checked_bytes(path, JOURNAL_SHA256).decode("utf-8").splitlines()
    if len(lines) != 1 + 2 * len(order):
        raise ValueError("probe journal row count differs")
    rows = [json.loads(line) for line in lines]
    if rows[0] != {
        "kind": "as_safety_extraction_v2_probe_v1",
        "protocol_sha256": protocol_sha,
        "expected_calls": len(order),
    }:
        raise ValueError("probe journal header differs")
    ends = []
    for index, expected in enumerate(order, 1):
        begin, end = rows[2 * index - 1 : 2 * index + 1]
        if begin != {"call_index": index, **expected, "event": "begin"}:
            raise ValueError("probe journal begin order differs")
        if (
            end.get("call_index") != index
            or end.get("case_id") != expected["case_id"]
            or end.get("method") != expected["method"]
            or end.get("event") != "end"
            or end.get("status") != "validated"
        ):
            raise ValueError("probe journal end order/status differs")
        ends.append(end)
    return ends


def audit(*, protocol_path: Path = PROTOCOL, journal_path: Path = JOURNAL) -> dict:
    protocol_bytes = _checked_bytes(protocol_path, PROTOCOL_SHA256)
    protocol = json.loads(protocol_bytes)
    if (
        protocol.get("kind") != "as_safety_extraction_v2_probe_v1"
        or protocol.get("case_order") != list(CASE_IDS)
        or protocol.get("candidate_generation") != {"max_window_tokens": 5, "max_candidates": 192}
        or not isinstance(protocol.get("request_order"), list)
    ):
        raise ValueError("probe protocol identity differs")
    for name, path in INPUTS.items():
        _checked_bytes(path, protocol["input_hashes"][name])
    generate, coverage_fn = _frozen_generator(protocol)
    cases = {
        case["id"]: case
        for case in load_development_cases(
            re_dataset=INPUTS["re_dataset"],
            v_dataset=INPUTS["v_dataset"],
            labels_path=INPUTS["labels"],
            spans_path=INPUTS["spans"],
            subject_path=INPUTS["subject"],
            owner_review_path=INPUTS["owner_review"],
        )
    }
    ends = _load_journal(journal_path, _sha(protocol_bytes), protocol["request_order"])
    id_rows = {row["case_id"]: row for row in ends if row["method"] == "ids"}
    if set(id_rows) != set(CASE_IDS) or len(id_rows) != len(CASE_IDS):
        raise ValueError("candidate-ID calls differ")
    rows = []
    for case_id in CASE_IDS:
        case = cases[case_id]
        message = case["user_message"]
        candidates = generate(message, **protocol["candidate_generation"])
        reviewed = {field: [case[f"{name}_reference"]] for field, name in FIELD_NAMES}
        coverage = coverage_fn(candidates, reviewed)
        recorded = id_rows[case_id]
        if (
            coverage != recorded["candidate_coverage"]
            or candidates.source_sha256 != recorded["candidate_source_sha256"]
            or len(candidates.candidates) != recorded["candidate_coverage"]["candidate_count"]
        ):
            raise ValueError(f"candidate coverage differs: {case_id}")
        by_id = {item.id: item for item in candidates.candidates}
        fields = {}
        for field, name in FIELD_NAMES:
            reference = case[f"{name}_reference"]
            status = coverage["by_field"][field]
            gold = next(
                (
                    item
                    for item in candidates.candidates
                    if (item.clause_index, item.quote)
                    == (reference["clause_index"], reference["quote"])
                ),
                None,
            )
            selected_id = recorded["selected_ids"][f"{name}_id"]
            selected = by_id.get(selected_id)
            if selected is None:
                raise ValueError(f"selected ID absent: {case_id} {name}")
            public_span = {
                key: getattr(selected, key)
                for key in ("clause_index", "start", "end", "quote_sha256")
            }
            hit = gold is not None and gold.id == selected_id
            if public_span != recorded["spans"][field] or hit != recorded["reference_hits"][field]:
                raise ValueError(f"selected span differs: {case_id} {name}")
            fields[name] = {
                "candidate_status": status,
                "gold_rank": int(gold.id[1:]) if gold else None,
                "chosen_rank": int(selected_id[1:]),
                "exact_selection": hit,
                "omission_reason": (
                    _failure_reason(
                        message, reference, protocol["candidate_generation"]["max_window_tokens"]
                    )
                    if status == "not_generated"
                    else None
                ),
            }
        rows.append(
            {
                "case_id": case_id,
                "candidate_count": len(candidates.candidates),
                "generated_count": len(candidates.generated),
                "fields": fields,
            }
        )
    all_fields = [field for row in rows for field in row["fields"].values()]
    return {
        "kind": "as_safety_candidate_probe_offline_audit_v1",
        "scope": "historical_already_exposed_development_only",
        "frozen_commit": protocol["frozen_code_commit"],
        "protocol_sha256": _sha(protocol_bytes),
        "journal_sha256": JOURNAL_SHA256,
        "denominator": len(all_fields),
        "included": sum(f["candidate_status"] == "selected" for f in all_fields),
        "truncated": sum(f["candidate_status"] == "truncated" for f in all_fields),
        "not_generated": sum(f["candidate_status"] == "not_generated" for f in all_fields),
        "exact_selection": sum(f["exact_selection"] for f in all_fields),
        "rows": rows,
    }


def current_lattice_sensitivity() -> dict:
    """Availability only; this later ES-tuned generator has no model selections."""
    audit()  # Pin historical inputs and journal before comparing later code.
    cases = {
        case["id"]: case
        for case in load_development_cases(
            re_dataset=INPUTS["re_dataset"],
            v_dataset=INPUTS["v_dataset"],
            labels_path=INPUTS["labels"],
            spans_path=INPUTS["spans"],
            subject_path=INPUTS["subject"],
            owner_review_path=INPUTS["owner_review"],
        )
    }
    settings = []
    for width in (5, 8):
        rows = []
        for case_id in CASE_IDS:
            case = cases[case_id]
            lattice = generate_source_lattice(
                case["user_message"], max_window_tokens=width, max_candidates=192
            )
            clauses = split_clauses(case["user_message"])
            fields = {}
            for _, name in FIELD_NAMES:
                reference = case[f"{name}_reference"]
                clause = clauses[reference["clause_index"] - 1]
                quote = reference["quote"]
                if clause.count(quote) != 1:
                    raise ValueError(f"ambiguous reference: {case_id} {name}")
                start = clause.index(quote)
                fields[name] = source_candidate_status(
                    lattice,
                    clause_index=reference["clause_index"],
                    start=start,
                    end=start + len(quote),
                )
            rows.append(
                {
                    "case_id": case_id,
                    "selected_candidates": len(lattice.candidates),
                    "generated_candidates": len(lattice.generated),
                    "fields": fields,
                }
            )
        statuses = [status for row in rows for status in row["fields"].values()]
        settings.append(
            {
                "max_window_tokens": width,
                "max_candidates": 192,
                "included": statuses.count("selected"),
                "truncated": statuses.count("truncated"),
                "not_generated": statuses.count("not_generated"),
                "rows": rows,
            }
        )
    return {
        "scope": "later_es_tuned_source_lattice_exposed_re_v_availability_only",
        "source_lattice_sha256": _sha(
            (ROOT / "experiments/as_safety_v2/source_lattice.py").read_bytes()
        ),
        "denominator": len(CASE_IDS) * len(FIELD_NAMES),
        "settings": settings,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-lattice-sensitivity", action="store_true")
    args = parser.parse_args()
    report = audit()
    if args.current_lattice_sensitivity:
        report["current_lattice_sensitivity"] = current_lattice_sensitivity()
    print(json.dumps(report, ensure_ascii=False, indent=2))
