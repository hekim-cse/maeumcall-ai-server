"""Compare exact compound wire heads and action-free coordinated source boundaries."""

import re
from functools import partial

from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_device_operation import PLACE_NAME, device_operation_source
from experiments.as_safety_explicit_source import NOUN_TAGS, DirectSource, strict_boundaries
from experiments.as_safety_multi_event_action import (
    DIRECT_LOCATIVE,
    MODIFIER,
    SECOND_EVENT,
    multi_event_boundaries,
)
from experiments.as_safety_source_scope import (
    PHYSICAL_HEADS,
    event_kinds,
    unresolved_on_same_event,
)
from experiments.as_safety_temporal_action import TIME_PREFIX

WIRE_HEADS = frozenset({"전원선", "접지선", "신호선"})
NOMINAL_TAGS = NOUN_TAGS | {"XSN"}
FIRST_EVENT = re.compile(rf"{MODIFIER}(?:불꽃이 튀었고|연기가 (?:났고|나왔고))")
FIRST_REPORT = re.compile(rf"{DIRECT_LOCATIVE}{FIRST_EVENT.pattern}")
SECOND_OBSERVATION = rf"{MODIFIER}연기가 보였습니다"
SECOND_REPORT = re.compile(rf"{DIRECT_LOCATIVE}(?:{SECOND_EVENT}|{SECOND_OBSERVATION})[.。]?")
TOPIC_TIME = re.compile(r"(?:오늘은|어제는|엊그제는) ")
CHANGE = re.compile(
    r"(?P<subject>[가-힣]+(?: [가-힣]+){0,5})(?:이|가) "
    r"(?:뜨거워지며|휘면서|부풀면서|녹으면서) "
    r"(?:[가-힣]+ ){0,4}[가-힣]+(?:이|가) (?:녹았습니다|벌어졌습니다|갈라졌습니다)"
)
CHANGE_HEADS = PHYSICAL_HEADS | {"옆면"}


def wire_evidence(quote: str, kiwi: Kiwi) -> bool:
    device, _, head = quote.rpartition(" ")
    return head in WIRE_HEADS and (
        not device or all(token.tag in NOMINAL_TAGS for token in kiwi.tokenize(device))
    )


def right_prefix(prefix: str) -> bool:
    preceding, comma, remainder = prefix.partition(", ")
    return (
        bool(comma)
        and FIRST_REPORT.fullmatch(preceding) is not None
        and (
            not remainder
            or TIME_PREFIX.fullmatch(remainder) is not None
            or TOPIC_TIME.fullmatch(remainder) is not None
        )
    )


def changed_subject(event: str) -> str | None:
    match = CHANGE.fullmatch(event)
    if match and match["subject"].split()[-1] in CHANGE_HEADS:
        return match["subject"]
    return None


def coordinated_boundaries(prefix: str, event: str, suffix: str) -> bool:
    if (not prefix or TIME_PREFIX.fullmatch(prefix)) and FIRST_EVENT.fullmatch(event):
        if suffix.startswith(", "):
            following = suffix[2:]
            if SECOND_REPORT.fullmatch(following):
                return True
            time = TOPIC_TIME.match(following) or TIME_PREFIX.match(following)
            statement = following[time.end() :] if time else following
            return changed_subject(statement.removesuffix(".").removesuffix("。")) is not None
    return (
        right_prefix(prefix)
        and re.fullmatch(SECOND_EVENT, event) is not None
        and strict_boundaries("", event, suffix)
    )


def coordinated_change(pair: FixedPair, occurrence: str, kiwi: Kiwi) -> DirectSource | None:
    event, candidate = pair.event, pair.candidate
    index, start, end = event["clause_index"], event["start"], event["end"]
    clause = pair.clauses[index - 1]
    if (
        occurrence == "observed"
        and candidate.clause_index == index
        and candidate.start == start
        and candidate.end == start + len(candidate.quote)
        and candidate.quote == changed_subject(event["quote"])
        and right_prefix(clause[:start])
        and strict_boundaries("", event["quote"], clause[end:])
        and all(token.tag in NOMINAL_TAGS for token in kiwi.tokenize(candidate.quote))
        and not is_place_name(candidate.quote, pair.clauses)
        and not unresolved_on_same_event(
            pair.clauses[index:], event_kinds(kiwi.tokenize(event["quote"])), kiwi
        )
    ):
        return DirectSource(index, candidate.start, candidate.end, start, end)
    return None


def is_place_name(quote: str, clauses: tuple[str, ...]) -> bool:
    pattern = re.compile(re.escape(quote) + PLACE_NAME)
    return any(pattern.fullmatch(clause) for clause in clauses)


def wire_coordination_source(
    pair: FixedPair, occurrence: str, kiwi: Kiwi, *, allow_wire: bool, allow_coordination: bool
) -> DirectSource | None:
    event, candidate = pair.event, pair.candidate
    clause = pair.clauses[event["clause_index"] - 1]

    def boundaries(prefix: str, quote: str, suffix: str) -> bool:
        return multi_event_boundaries(prefix, quote, suffix) or (
            allow_coordination and coordinated_boundaries(prefix, quote, suffix)
        )

    def additional_nominal(quote: str) -> bool:
        if is_place_name(quote, pair.clauses):
            return False
        if allow_wire and wire_evidence(quote, kiwi):
            return True
        return (
            allow_coordination
            and quote.startswith("다른 기기의 ")
            and quote.removeprefix("다른 기기의 ") in PHYSICAL_HEADS
            and coordinated_boundaries(
                clause[: candidate.start], event["quote"], clause[event["end"] :]
            )
        )

    result = device_operation_source(
        pair, occurrence, kiwi, boundaries=boundaries, additional_nominal=additional_nominal
    )
    if result is None and allow_coordination:
        return coordinated_change(pair, occurrence, kiwi)
    return result


DETECTORS = {
    "baseline": partial(device_operation_source, boundaries=multi_event_boundaries),
    "wire_only": partial(wire_coordination_source, allow_wire=True, allow_coordination=False),
    "coordination_only": partial(
        wire_coordination_source, allow_wire=False, allow_coordination=True
    ),
    "combined": partial(wire_coordination_source, allow_wire=True, allow_coordination=True),
}
