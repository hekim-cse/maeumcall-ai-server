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
EXTENDED_FUNCTIONS = PART_FUNCTIONS | {"여과"}
EXTENDED_SHAPES = PART_SHAPES | {"격자"}


def part_splits(
    part: str, functions: frozenset[str], shapes: frozenset[str]
) -> set[tuple[str, str]]:
    return {
        (part[: -len(shape)], shape)
        for shape in shapes
        if part.endswith(shape) and part[: -len(shape)] in functions
    }


def names_device_component(quote: str) -> bool:
    device, separator, part = quote.rpartition(" ")
    if not separator or device not in DEVICE_NAMES:
        return False
    return bool(part_splits(part, PART_FUNCTIONS, PART_SHAPES))


def has_unique_device_split(
    quote: str,
    devices: frozenset[str],
    functions: frozenset[str],
    shapes: frozenset[str],
) -> bool:
    matches = set()
    for device in devices:
        if not quote.startswith(device):
            continue
        part = quote[len(device) :].removeprefix(" ")
        matches.update(
            (device, function, shape) for function, shape in part_splits(part, functions, shapes)
        )
    return len(matches) == 1


def names_extended_component(quote: str) -> bool:
    """Recognize the whole source phrase, including an omitted boundary space."""
    return has_unique_device_split(quote, DEVICE_NAMES, EXTENDED_FUNCTIONS, EXTENDED_SHAPES)


def composed_source(pair: FixedPair, occurrence: str, kiwi: Kiwi) -> DirectSource | None:
    return contextual_source(pair, occurrence, kiwi, extra_part_evidence=names_device_component)


def surface_nominal_source(pair: FixedPair, occurrence: str, kiwi: Kiwi) -> DirectSource | None:
    """Use the exact device/part surface as nominal evidence for this variant."""
    return contextual_source(
        pair,
        occurrence,
        kiwi,
        extra_part_evidence=names_device_component,
        nominal_evidence=names_device_component,
    )


def attached_device_source(pair: FixedPair, occurrence: str, kiwi: Kiwi) -> DirectSource | None:
    return contextual_source(
        pair,
        occurrence,
        kiwi,
        extra_part_evidence=names_extended_component,
        nominal_evidence=names_extended_component,
    )
