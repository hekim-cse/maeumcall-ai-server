"""Validate provenance and exact quotations for a development-only support probe."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.action_field_dev_cases import load_cases as load_dev_cases
from scripts.fresh_scope_ai_cases import load_cases as load_fresh_cases

CLAIM_SOURCE = (
    Path(__file__).resolve().parent / "data/exploratory/semantic-support-claims-2026-11-05.json"
)
VERDICTS = frozenset({"supported", "contradicted", "insufficient"})


def load_claims(path: Path = CLAIM_SOURCE) -> list[dict]:
    source = json.loads(path.read_text(encoding="utf-8"))
    if (
        source.get("kind") != "exploratory_semantic_support_claims_v1"
        or source.get("not_official_test") is not True
        or source.get("provenance") != "ai_assisted_unreviewed_previously_exposed_development_cases"
    ):
        raise ValueError("semantic claims must remain exploratory development data")
    cases = {case["id"]: case for case in [*load_fresh_cases(), *load_dev_cases()]}
    claims = source.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ValueError("semantic claims must be a nonempty list")
    ids = set()
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {
            "id",
            "case_id",
            "field",
            "value",
            "quote",
            "expected",
        }:
            raise ValueError("semantic claim shape invalid")
        if claim["id"] in ids or claim["expected"] not in VERDICTS:
            raise ValueError("semantic claim id or verdict invalid")
        ids.add(claim["id"])
        case = cases[claim["case_id"]]
        if claim["field"] not in case["labels"]["fields"]:
            raise ValueError("semantic claim field is outside scenario contract")
        if not isinstance(claim["value"], str) or not claim["value"].strip():
            raise ValueError("semantic claim value invalid")
        quote = claim["quote"]
        if (
            not isinstance(quote, str)
            or not quote.strip()
            or case["user_message"].count(quote) != 1
        ):
            raise ValueError("semantic claim quote must occur exactly once")
        label = case["labels"]["fields"][claim["field"]]
        if claim["expected"] == "supported":
            if label is None or claim["value"] not in label["accepted_values"]:
                raise ValueError("supported claim disagrees with exploratory label")
        elif label is not None:
            raise ValueError("unsupported claim requires a blank exploratory label")
    return [{**claim, "utterance": cases[claim["case_id"]]["user_message"]} for claim in claims]
