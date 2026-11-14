"""Load user-reviewed, AI-authored v4 cases without exposing gold to prompts."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v4.contract import MAX_EVENTS, route_for_events

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "docs/portfolio/nlu_safety_event_source_v4_review.md"
FIELD_REVIEW = ROOT / "docs/portfolio/nlu_safety_event_source_v4_field_review.md"
CASE_IDS = tuple(f"ES{index:02}" for index in range(1, 21))
ROUTES = {
    "안전 우선": "safety_action_required",
    "상태 확인": "confirming_safety_status",
    "일반 접수": "collecting_service_request",
}
CASE_FIELDS = {
    "id",
    "user_message",
    "utterance_sha256",
    "target",
    "events",
    "expected_route",
    "overflow",
}
EVENT_FIELDS = {"event_span", "occurrence", "hazard_owner_span", "owner_to_target"}
SPAN_FIELDS = {"clause_index", "quote"}
_MENTION = re.compile(r"(\d+) `([^`]+)`\Z")
_EVENT = re.compile(r"(\d+) `([^`]+)` / (observed|uncertain|nonoccurring)\Z")
_OWNER = re.compile(r"(\d+) `([^`]+)` / (current|other|unknown)\Z")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _source_rows() -> dict[str, dict]:
    """Rebuild approved rows from the two review tables, not from model data."""
    utterances = {}
    for line in REVIEW.read_text(encoding="utf-8").splitlines():
        if line.startswith("| ES"):
            columns = [column.strip() for column in line.strip("|").split("|")]
            if len(columns) != 5 or columns[0] in utterances:
                raise ValueError("utterance review table differs")
            utterances[columns[0]] = columns[1]
    if tuple(utterances) != CASE_IDS:
        raise ValueError("utterance review order differs")

    cases: dict[str, dict] = {}
    for line in FIELD_REVIEW.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ES"):
            continue
        columns = [column.strip() for column in line.strip("|").split("|")]
        if len(columns) != 6:
            raise ValueError("field review table differs")
        case_id, target_text, event_text, owner_text, route_text, _ = columns
        target_match = _MENTION.fullmatch(target_text)
        event_match = _EVENT.fullmatch(event_text)
        if not target_match or not event_match or route_text not in ROUTES:
            raise ValueError(f"field review row differs: {case_id}")
        target = {"clause_index": int(target_match[1]), "quote": target_match[2]}
        event = {
            "event_span": {"clause_index": int(event_match[1]), "quote": event_match[2]},
            "occurrence": event_match[3],
            "hazard_owner_span": None,
            "owner_to_target": None,
        }
        if owner_text == "`null` / unknown":
            event["owner_to_target"] = "unknown"
        elif owner_text != "—":
            owner_match = _OWNER.fullmatch(owner_text)
            if not owner_match:
                raise ValueError(f"owner review row differs: {case_id}")
            event["hazard_owner_span"] = {
                "clause_index": int(owner_match[1]),
                "quote": owner_match[2],
            }
            event["owner_to_target"] = owner_match[3]
        if case_id not in utterances:
            raise ValueError(f"unexpected field review ID: {case_id}")
        if case_id not in cases:
            message = utterances[case_id]
            cases[case_id] = {
                "id": case_id,
                "user_message": message,
                "utterance_sha256": _sha256(message.encode("utf-8")),
                "target": target,
                "events": [],
                "expected_route": ROUTES[route_text],
                "overflow": False,
            }
        if (
            cases[case_id]["target"] != target
            or cases[case_id]["expected_route"] != ROUTES[route_text]
        ):
            raise ValueError(f"field review target or route differs: {case_id}")
        cases[case_id]["events"].append(event)
    if tuple(cases) != CASE_IDS or sum(len(case["events"]) for case in cases.values()) != 22:
        raise ValueError("field review case or event count differs")
    return cases


def _validate_case(case: dict) -> None:
    if type(case) is not dict or set(case) != CASE_FIELDS:
        raise ValueError("case fields differ")
    message = case["user_message"]
    if type(message) is not str or _sha256(message.encode("utf-8")) != case["utterance_sha256"]:
        raise ValueError("utterance hash differs")
    clauses = split_clauses(message)
    target = case["target"]
    if type(target) is not dict or set(target) != SPAN_FIELDS:
        raise ValueError("target fields differ")
    anchor_span(target, clauses, field="target")
    if type(target["clause_index"]) is not int or type(target["quote"]) is not str:
        raise ValueError("target type differs")
    if type(case["overflow"]) is not bool or case["overflow"]:
        raise ValueError("reviewed overflow differs")
    events = case["events"]
    if type(events) is not list or not 1 <= len(events) <= MAX_EVENTS:
        raise ValueError("reviewed event count differs")
    checked = []
    relations = []
    previous_end: tuple[int, int] | None = None
    for event in events:
        if type(event) is not dict or set(event) != EVENT_FIELDS:
            raise ValueError("event fields differ")
        event_span = event["event_span"]
        if type(event_span) is not dict or set(event_span) != SPAN_FIELDS:
            raise ValueError("event span fields differ")
        anchored = anchor_span(event_span, clauses, field="event_span")
        if anchored is None:
            raise ValueError("event span absent")
        position = anchored["clause_index"], anchored["start"]
        if previous_end is not None and position < previous_end:
            raise ValueError("event spans overlap or differ in order")
        previous_end = anchored["clause_index"], anchored["end"]
        occurrence = event["occurrence"]
        relation = event["owner_to_target"]
        owner = event["hazard_owner_span"]
        if type(occurrence) is not str or occurrence not in {
            "observed",
            "uncertain",
            "nonoccurring",
        }:
            raise ValueError("event occurrence differs")
        if occurrence == "nonoccurring":
            if owner is not None or relation is not None:
                raise ValueError("nonoccurring owner differs")
        elif type(relation) is not str or relation not in {"current", "other", "unknown"}:
            raise ValueError("event relation differs")
        elif relation != "unknown" and owner is None:
            raise ValueError("event owner missing")
        if owner is not None:
            if type(owner) is not dict or set(owner) != SPAN_FIELDS:
                raise ValueError("owner span fields differ")
            anchor_span(owner, clauses, field="hazard_owner_span")
        checked.append({"occurrence": occurrence})
        relations.append(relation)
    if route_for_events(checked, relations) != case["expected_route"]:
        raise ValueError("reviewed route differs")


def load_cases(path: Path) -> list[dict]:
    """Reject review drift, data tampering and ill-formed event references."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if type(payload) is not dict or set(payload) != {
        "kind",
        "provenance",
        "review_status",
        "review_date",
        "source_sha256",
        "cases",
    }:
        raise ValueError("dataset fields differ")
    if (
        payload["kind"] != "as_safety_event_source_v4_exploration_reviewed_v1"
        or payload["provenance"] != "ai_authored_user_reviewed_exploration"
        or payload["review_status"] != "owner_approved_for_exploratory_evaluation"
        or payload["review_date"] != "2026-11-15"
        or payload["source_sha256"]
        != {
            "utterances": _sha256(REVIEW.read_bytes()),
            "fields": _sha256(FIELD_REVIEW.read_bytes()),
        }
    ):
        raise ValueError("review provenance differs")
    cases = payload["cases"]
    if (
        type(cases) is not list
        or tuple(case.get("id") for case in cases if type(case) is dict) != CASE_IDS
    ):
        raise ValueError("case ID order differs")
    source = _source_rows()
    if len(cases) != len(source):
        raise ValueError("case count differs")
    for case in cases:
        _validate_case(case)
        if case != source[case["id"]]:
            raise ValueError(f"reviewed values differ: {case['id']}")
    return cases
