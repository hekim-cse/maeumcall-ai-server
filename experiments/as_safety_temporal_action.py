"""Independent boundary relaxations for an anchored locative source."""

import re
from functools import partial

from experiments.as_safety_device_operation import device_operation_source
from experiments.as_safety_explicit_source import strict_boundaries

TIME_PREFIX = re.compile(r"(?:(?:오늘|어제|엊그제)(?: (?:아침|오전|오후|저녁|밤))?|방금|조금 전) ")
OBSERVED_CONNECTIVE = re.compile(r"(?:불꽃이 튀(?:어|어서)|연기가 (?:나서|나와(?:서)?))")
COMPLETED_ACTION = re.compile(
    r" (?:바로 )?(?:전원을 (?:껐|차단했)|플러그를 뽑았|작동을 멈췄)습니다[.。]?"
)


def locative_boundaries(
    prefix: str, event: str, suffix: str, *, allow_time: bool, allow_action: bool
) -> bool:
    prefix_ok = not prefix or (allow_time and TIME_PREFIX.fullmatch(prefix) is not None)
    suffix_ok = strict_boundaries("", event, suffix) or (
        allow_action
        and OBSERVED_CONNECTIVE.fullmatch(event) is not None
        and COMPLETED_ACTION.fullmatch(suffix) is not None
    )
    return prefix_ok and suffix_ok


RULES = {
    "baseline": device_operation_source,
    "time_only": partial(
        device_operation_source,
        boundaries=partial(locative_boundaries, allow_time=True, allow_action=False),
    ),
    "action_only": partial(
        device_operation_source,
        boundaries=partial(locative_boundaries, allow_time=False, allow_action=True),
    ),
    "time_and_action": partial(
        device_operation_source,
        boundaries=partial(locative_boundaries, allow_time=True, allow_action=True),
    ),
}
