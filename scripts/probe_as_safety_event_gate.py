"""Development-only evidence gate for a model's direct A/S safety decision.

This selective gate can only defer a direct decision. It cannot promote a
model's normal decision to immediate protection, so missed hazards remain a
separate problem. It is not connected to the service graph.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from scripts.probe_as_safety_clause_index import split_clauses

DIRECT = "safety_action_required"
CONFIRM = "confirming_safety_status"
NORMAL = "collecting_service_request"

_OBSERVED_EVENTS = tuple(
    re.compile(pattern)
    for pattern in (
        r"(?:불꽃|스파크)[^.!?\n]{0,18}(?:튀었|튀어|튀었습니다|나왔|발생했)",
        r"(?:배터리|하판|케이스)[^.!?\n]{0,28}"
        r"(?:솟아올|부풀(?:었|어|고|었습니다)|팽창(?:했|합니다)|볼록(?:하|해)|변형(?:돼|됐|되어))",
        r"(?:타는|매캐한)[^.!?\n]{0,12}냄새[^.!?\n]{0,16}(?:나서|납니다|나요|났|맡았)",
        r"(?:액체|전해액)[^.!?\n]{0,16}(?:새어|새고|누출)",
        r"(?:뜨거워|뜨겁|고열)",
        r"(?:그을|녹았|녹아|녹았습니다)",
        r"(?:피복|전선)[^.!?\n]{0,24}(?:갈라|벗겨|끊어|노출)",
        r"(?:연기|연무)[^.!?\n]{0,16}(?:피어|나서|납니다|나요|났|올라|발생)",
    )
)
_HYPOTHETICAL_EVENT = re.compile(
    r"(?:불꽃|스파크|연기|연무|타는\s*냄새|배터리)[^.!?\n]{0,18}"
    r"(?:튀면|나면|부풀면|팽창하면|발생하면|생기면)"
)
_NEGATED_EVENT = re.compile(
    r"(?:불꽃|연기|연무|타는\s*냄새|배터리)[^.!?\n]{0,24}"
    r"(?:나지\s*않|부풀지\s*않|보이지\s*않|없습니다|없어요)"
)
_UNCERTAIN = re.compile(r"(?:것처럼|듯합니다|듯해요|모르겠|확신이\s*없)")
_DISPLAY_ONLY = re.compile(r"(?:아이콘|그림|화면\s*표시|안내\s*사진)")
_QUESTION_ONLY = re.compile(r"(?:확인하는\s*방법|조치\s*방법|수리비|가능한지)")


@dataclass(frozen=True)
class GateDecision:
    route: str
    reason: str


def gate_direct_safety(utterance: str, model_row: dict) -> GateDecision:
    """Require an observed hazard in the selected source clause before direct routing."""
    route = model_row["route"]
    if route != DIRECT:
        return GateDecision(route=route, reason="model_route_unchanged")
    clauses = split_clauses(utterance)
    index = model_row["evidence_index"]
    if type(index) is not int or not 1 <= index <= len(clauses):
        raise ValueError("direct safety decision lacks a valid source clause")
    source = clauses[index - 1]
    if _UNCERTAIN.search(source):
        return GateDecision(route=CONFIRM, reason="uncertain_observation")
    if any(pattern.search(source) for pattern in _OBSERVED_EVENTS):
        return GateDecision(route=DIRECT, reason="observed_event_in_source")
    if _DISPLAY_ONLY.search(source):
        return GateDecision(route=NORMAL, reason="display_or_document_mention")
    if _HYPOTHETICAL_EVENT.search(source):
        return GateDecision(route=NORMAL, reason="hypothetical_event")
    if _NEGATED_EVENT.search(source):
        return GateDecision(route=NORMAL, reason="negated_event")
    if _QUESTION_ONLY.search(source):
        return GateDecision(route=NORMAL, reason="question_without_observation")
    return GateDecision(route=CONFIRM, reason="missing_observed_event_in_source")
