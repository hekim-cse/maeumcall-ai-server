"""Keep direct source proof local to the event on either side of a completed action."""

import re
from functools import partial

from experiments.as_safety_device_operation import device_operation_source
from experiments.as_safety_temporal_action import (
    ACTION_STEM,
    OBSERVED_CONNECTIVE,
    RULES,
    TIME_PREFIX,
    locative_boundaries,
)

MODIFIER = r"(?:(?:작은|큰|짧은|파란|옅은|희미한) )?"
DIRECT_LOCATIVE = r"(?:[가-힣]+ ){0,10}[가-힣]+(?:에서는|에서|로부터|으로부터) "
ACTION_JOIN = rf"{ACTION_STEM}고"
FIRST_REPORT = re.compile(rf"{DIRECT_LOCATIVE}{MODIFIER}{OBSERVED_CONNECTIVE.pattern}{ACTION_JOIN}")
SECOND_EVENT = rf"{MODIFIER}(?:불꽃이 튀었습니다|연기가 (?:났습니다|나왔습니다)|연기를 봤습니다)"
SECOND_REPORT = re.compile(rf"{DIRECT_LOCATIVE}{SECOND_EVENT}[.。]?")
SEPARATE_SOUND = re.compile(r"(?:뒤이어 )?경고 소리가 났지만 그 소리의 출처는 모르겠습니다[.。]?")
FIRST_EVENT = re.compile(rf"{MODIFIER}{OBSERVED_CONNECTIVE.pattern}")
ACTION_BOUNDARY = re.compile(ACTION_JOIN)


def multi_event_boundaries(prefix: str, event: str, suffix: str) -> bool:
    if locative_boundaries(prefix, event, suffix, allow_time=True, allow_action=True):
        return True

    action, comma, following = suffix.partition(", ")
    if comma:
        return (
            (not prefix or TIME_PREFIX.fullmatch(prefix) is not None)
            and FIRST_EVENT.fullmatch(event) is not None
            and ACTION_BOUNDARY.fullmatch(action) is not None
            and (
                SECOND_REPORT.fullmatch(following) is not None
                or SEPARATE_SOUND.fullmatch(following) is not None
            )
        )

    preceding, comma, after_join = prefix.partition(", ")
    return (
        bool(comma)
        and (not after_join or TIME_PREFIX.fullmatch(after_join) is not None)
        and FIRST_REPORT.fullmatch(preceding) is not None
        and re.fullmatch(SECOND_EVENT, event) is not None
        and suffix in {"", ".", "。"}
    )


DETECTORS = {
    "baseline": RULES["time_and_action"],
    "multi_event": partial(device_operation_source, boundaries=multi_event_boundaries),
}
