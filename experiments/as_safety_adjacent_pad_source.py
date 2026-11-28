"""Recover a direct charging-pad source without treating adjacency as ownership."""

import re
from functools import partial

from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_device_operation import device_operation_source
from experiments.as_safety_explicit_source import DirectSource
from experiments.as_safety_source_scope import event_kinds
from experiments.as_safety_temporal_action import (
    OBSERVED_CONNECTIVE,
    TIME_PREFIX,
    locative_boundaries,
)
from experiments.as_safety_wire_coordination import CORRECTION, is_place_name
from experiments.as_safety_wire_coordination import DETECTORS as PREVIOUS

CHARGING_PAD = re.compile(r"(?:(?:차량용|탁상용|휴대용|가정용) )?(?:무선 )?충전 패드")
COLLOQUIAL_ACTION = re.compile(
    r" (?:바로 )?(?:전원을 (?:뺐|껐|차단했)|플러그를 (?:뺐|뽑았))어요[.。]?"
)


def pad_nominal(quote: str) -> bool:
    return CHARGING_PAD.fullmatch(quote) is not None


def adjacent_action_boundaries(
    prefix: str, event: str, suffix: str, *, has_prior_clause: bool
) -> bool:
    if has_prior_clause and prefix == "그 옆의 ":
        prefix = ""
    return locative_boundaries(prefix, event, suffix, allow_time=True, allow_action=True) or (
        (not prefix or TIME_PREFIX.fullmatch(prefix) is not None)
        and OBSERVED_CONNECTIVE.fullmatch(event) is not None
        and COLLOQUIAL_ACTION.fullmatch(suffix) is not None
    )


def adjacent_pad_source(pair: FixedPair, occurrence: str, kiwi: Kiwi) -> DirectSource | None:
    established = PREVIOUS["combined"](pair, occurrence, kiwi)
    if established is not None or occurrence != "observed":
        return established
    index = pair.event["clause_index"]
    if is_place_name(pair.candidate.quote, pair.clauses):
        return None
    kinds = event_kinds(kiwi.tokenize(pair.event["quote"]))
    if any(
        CORRECTION.match(clause) and not kinds.isdisjoint(event_kinds(kiwi.tokenize(clause)))
        for clause in pair.clauses[index:]
    ):
        return None
    return device_operation_source(
        pair,
        occurrence,
        kiwi,
        boundaries=partial(adjacent_action_boundaries, has_prior_clause=index > 1),
        additional_nominal=pad_nominal,
    )


DETECTORS = {"baseline": PREVIOUS["combined"], "adjacent_pad": adjacent_pad_source}
