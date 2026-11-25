"""Use an earlier affirmative operation as evidence for an unregistered device."""

import re

from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_device_context import device_context_source
from experiments.as_safety_explicit_source import NOUN_TAGS, DirectSource

OPERATION = re.compile(
    r"(?P<name>[가-힣]+)의 전원 (?:버튼을 눌렀습니다|"
    r"스위치를 (?:켰습니다|껐습니다)|플러그를 뽑았습니다)[.。]?"
)
PLACE_NAME = r"(?:은|는) (?:[가-힣]+ )*(?:구역|장소|공간|작업실|보관함) 이름입니다[.。]?"


def device_operation_source(pair: FixedPair, occurrence: str, kiwi: Kiwi) -> DirectSource | None:
    """Reuse locative guards and add only evidence for the candidate's exact device name."""
    device, separator, _ = pair.candidate.quote.rpartition(" ")
    before_event = pair.clauses[: pair.event["clause_index"] - 1]
    if separator and any(
        (match := OPERATION.fullmatch(clause)) and match["name"] == device
        for clause in before_event
    ):
        tokens = kiwi.tokenize(device)
        # A power switch can also belong to a room. Require a noun ending in
        # the nominal device suffix as complementary evidence for this path.
        if (
            len(tokens) >= 2
            and (tokens[-1].form, tokens[-1].tag) == ("기", "XSN")
            and all(token.tag in NOUN_TAGS for token in tokens[:-1])
            and not any(
                re.fullmatch(re.escape(device) + PLACE_NAME, clause) for clause in pair.clauses
            )
        ):
            return device_context_source(pair, occurrence, kiwi, extra_devices=frozenset({device}))
    return device_context_source(pair, occurrence, kiwi)
