"""Recover full surface part names and explicit part links in earlier context."""

import re
from collections.abc import Callable

from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_explicit_source import (
    BoundaryCheck,
    DirectSource,
    explicit_source,
    strict_boundaries,
)
from experiments.as_safety_source_role import changed_subject_end, is_perception
from experiments.as_safety_source_scope import (
    PHYSICAL_HEADS,
    event_kinds,
    source_scope,
    unresolved_on_same_event,
)

DEVICE = r"(?P<device>[가-힣]+(?: [가-힣]+)*)"
POSITION_HEADS = {
    "옆",
    "앞",
    "뒤",
    "주변",
    "아래",
    "위",
    "안",
    "내부",
    "바닥",
    "보관함",
    "선반",
    "근처",
}
RETRACTION = re.compile(r"분리했|떼어|제거했|장착하지|장착되지|잘못")


def has_explicit_part_link(part: str, preceding: tuple[str, ...]) -> bool:
    """Require an affirmative, uniquely named owner for the exact source phrase."""
    if not part or part.split()[-1] in POSITION_HEADS:
        return False
    escaped = re.escape(part)
    patterns = (
        re.compile(rf"{escaped}(?:은|는) {DEVICE}에 장착된 부품입니다[.。]?"),
        re.compile(rf"{DEVICE}의 (?:교체 )?부품인 {escaped}(?:을|를) 점검했습니다[.。]?"),
    )
    owners = set()
    for clause in preceding:
        if part in clause and RETRACTION.search(clause):
            return False
        for pattern in patterns:
            match = pattern.fullmatch(clause)
            if match and match["device"].split()[-1] in PHYSICAL_HEADS:
                owners.add(match["device"])
    return len(owners) == 1


def contextual_source(
    pair: FixedPair,
    occurrence: str,
    kiwi: Kiwi,
    *,
    extra_part_evidence: Callable[[str], bool] | None = None,
    nominal_evidence: Callable[[str], bool] | None = None,
    boundaries: BoundaryCheck = strict_boundaries,
) -> DirectSource | None:
    """Extend only the prior rule's locative head check, retaining its vetoes."""
    established = source_scope(pair, occurrence, kiwi, boundaries=boundaries)
    if established is not None:
        return established
    locative = explicit_source(
        pair, occurrence, kiwi, nominal_evidence=nominal_evidence, boundaries=boundaries
    )
    if locative is None:
        return None
    index = locative.clause_index
    event_tokens = kiwi.tokenize(pair.event["quote"])
    if (
        is_perception(event_tokens)
        or changed_subject_end(event_tokens) is not None
        or unresolved_on_same_event(pair.clauses[index:], event_kinds(event_tokens), kiwi)
    ):
        return None
    source = pair.candidate.quote
    surface_head = source.split()[-1]
    if surface_head in PHYSICAL_HEADS or has_explicit_part_link(source, pair.clauses[: index - 1]):
        return locative
    if extra_part_evidence is not None and extra_part_evidence(source):
        return locative
    return None
