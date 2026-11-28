"""Conservative source evidence with an explicit event scope."""

import re

from kiwipiepy import Kiwi, Token

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_explicit_source import (
    BoundaryCheck,
    DirectSource,
    explicit_source,
    strict_boundaries,
)
from experiments.as_safety_source_role import SOURCE_UNKNOWN, changed_subject_end, is_perception

# A small positive vocabulary for unambiguous appliance/part heads. Unknown
# heads abstain in the locative path, rather than treating every noun as a device.
PHYSICAL_HEADS = frozenset(
    {
        "단자",
        "포트",
        "송풍구",
        "배출구",
        "모터",
        "펌프",
        "배터리",
        "플러그",
        "장치",
        "어댑터",
        "충전기",
        "멀티탭",
        "전선",
        "커넥터",
    }
)
EVENT_KINDS = {
    "연기": "smoke",
    "냄새": "odor",
    "악취": "odor",
    "불꽃": "spark",
    "스파크": "spark",
    "소리": "sound",
    "소음": "sound",
    "부풀": "deformation",
    "갈라지": "deformation",
    "휘": "deformation",
    "녹": "deformation",
}
EXPLICIT_SCOPE = re.compile(
    r"(?<![가-힣])(?P<event>연기|냄새|악취|불꽃|스파크|소리|소음)"
    r"(?:의|이|가|은|는)?\s+(?:출처|어디서)"
)


def event_kinds(tokens: list[Token]) -> set[str]:
    return {
        EVENT_KINDS[token.form]
        for token in tokens
        if (token.tag.startswith("NN") or token.tag == "VV") and token.form in EVENT_KINDS
    }


def unresolved_on_same_event(following: tuple[str, ...], kinds: set[str], kiwi: Kiwi) -> bool:
    for clause in following:
        if not SOURCE_UNKNOWN.search(clause):
            continue
        mentioned = event_kinds(kiwi.tokenize(clause))
        scoped = {EVENT_KINDS[match["event"]] for match in EXPLICIT_SCOPE.finditer(clause)}
        # Smoke and odor may describe the same episode. Preserve uncertainty
        # unless a single, explicitly scoped separate type can be identified.
        smoke_or_odor = {"smoke", "odor"}
        clearly_separate = (
            len(kinds) == len(mentioned) == 1
            and mentioned == scoped
            and kinds.isdisjoint(mentioned)
            and not (kinds | mentioned) <= smoke_or_odor
        )
        if not clearly_separate:
            return True
    return False


def source_scope(
    pair: FixedPair,
    occurrence: str,
    kiwi: Kiwi,
    *,
    boundaries: BoundaryCheck = strict_boundaries,
) -> DirectSource | None:
    """Approve locally grounded material evidence, with conservative abstention."""
    locative = explicit_source(pair, occurrence, kiwi, boundaries=boundaries)
    if occurrence != "observed":
        return None
    event, candidate = pair.event, pair.candidate
    index, start, end = event["clause_index"], event["start"], event["end"]
    tokens = kiwi.tokenize(event["quote"])
    if is_perception(tokens) or unresolved_on_same_event(
        pair.clauses[index:], event_kinds(tokens), kiwi
    ):
        return None
    subject_end = changed_subject_end(tokens)
    if subject_end is not None:
        if (
            pair.clauses[index - 1][end:] in {"", ".", "。"}
            and candidate.clause_index == index
            and (candidate.start, candidate.end) == (start, start + subject_end)
        ):
            return DirectSource(index, candidate.start, candidate.end, start, end)
        return None
    if locative is None:
        return None
    words = kiwi.tokenize(candidate.quote)
    return locative if words and words[-1].form in PHYSICAL_HEADS else None
