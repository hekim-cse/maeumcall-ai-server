"""Recognize unambiguous registered aliases and names typed by the utterance."""

import re

from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_contextual_part import POSITION_HEADS, contextual_source
from experiments.as_safety_device_part import (
    DEVICE_NAMES,
    EXTENDED_FUNCTIONS,
    EXTENDED_SHAPES,
    part_splits,
)
from experiments.as_safety_explicit_source import DirectSource

DEVICE_STATEMENT = re.compile(
    r"(?P<name>[가-힣]+(?: [가-힣]+)*)(?:은|는) "
    r"(?:제가 |지금 |현재 )?(?:사용하는|사용 중인|점검할) (?:기기|장비)입니다[.。]?"
)
DEVICE_RETRACTION = r"(?:은|는) (?:(?:제가 |지금 |현재 )?(?:사용하는|사용 중인|점검할) )?(?:기기|장비)가 (?:아닙니다|아니라)"
DEVICE_MULTIPLICITY = r"(?:이)?라는 이름의 (?:기기|장비)가 (?:두|세|여러) 대 있습니다[.。]?"


def described_devices(preceding: tuple[str, ...], clauses: tuple[str, ...]) -> frozenset[str]:
    """Use only a named device explicitly introduced before the event."""
    names = {match["name"] for clause in preceding if (match := DEVICE_STATEMENT.fullmatch(clause))}
    return frozenset(
        name
        for name in names
        if name.split()[-1] not in POSITION_HEADS
        and not any(
            re.match(re.escape(name) + DEVICE_RETRACTION, clause)
            or re.fullmatch(re.escape(name) + DEVICE_MULTIPLICITY, clause)
            for clause in clauses
        )
    )


def unique_contextual_split(
    quote: str, registered: frozenset[str], described: frozenset[str]
) -> bool:
    matches = set()
    for device in registered | described:
        if device in registered:
            aliases = {device, device.replace(" ", "")}
            prefixes = {prefix for alias in aliases for prefix in (alias, f"{alias} ")}
        else:
            prefixes = {f"{device} "}
        for prefix in prefixes:
            if quote.startswith(prefix):
                part = quote[len(prefix) :]
                matches.update(
                    (device, function, shape)
                    for function, shape in part_splits(part, EXTENDED_FUNCTIONS, EXTENDED_SHAPES)
                )
    return len(matches) == 1


def device_context_source(pair: FixedPair, occurrence: str, kiwi: Kiwi) -> DirectSource | None:
    index = pair.event["clause_index"]
    described = described_devices(pair.clauses[: index - 1], pair.clauses)

    def nominal_evidence(quote: str) -> bool:
        return unique_contextual_split(quote, DEVICE_NAMES, described)

    return contextual_source(
        pair,
        occurrence,
        kiwi,
        extra_part_evidence=nominal_evidence,
        nominal_evidence=nominal_evidence,
    )
