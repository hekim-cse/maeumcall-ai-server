"""Recognize a narrow device + functional component construction."""

from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_contextual_part import contextual_source
from experiments.as_safety_explicit_source import DirectSource

# Recognize known device names as complete phrases rather than accepting any noun
# or suffix as a device. The function and shape vocabularies are independent.
DEVICE_NAMES = frozenset(
    {
        "인쇄기",
        "프린터",
        "공기청정기",
        "제습기",
        "정수기",
        "세탁기",
        "건조기",
        "전기담요",
        "선풍기",
        "전원 공급기",
        "전원 장치",
        "충전기",
        "어댑터",
        "모터",
        "펌프",
    }
)
PART_FUNCTIONS = frozenset({"집진", "절연", "차폐", "방열", "발열", "완충", "고정", "냉각"})
PART_SHAPES = frozenset({"판", "망", "막", "체", "편", "패드"})


def names_device_component(quote: str) -> bool:
    device, separator, part = quote.rpartition(" ")
    if not separator or device not in DEVICE_NAMES:
        return False
    return any(
        part.endswith(shape) and part[: -len(shape)] in PART_FUNCTIONS for shape in PART_SHAPES
    )


def composed_source(pair: FixedPair, occurrence: str, kiwi: Kiwi) -> DirectSource | None:
    return contextual_source(pair, occurrence, kiwi, extra_part_evidence=names_device_component)
