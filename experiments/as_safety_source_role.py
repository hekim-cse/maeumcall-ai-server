"""Distinguish changed entities from observation locations in anchored reports."""

import re
from itertools import pairwise

from kiwipiepy import Kiwi, Token

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_explicit_source import NOUN_TAGS, DirectSource, explicit_source

CHANGE_VERBS = {"부풀", "갈라지", "녹", "휘"}
SOURCE_UNKNOWN = re.compile(
    r"(?:출처(?:를|는|가)?\s*|"
    r"(?:어디서|어느 [가-힣 ]{1,16}에서)[^.?!]*(?:났|나왔|시작|튀|생겼)[^.?!]*)"
    r"(?:모르|확인하지 못|알 수 없)"
)


def changed_subject_end(tokens: list[Token]) -> int | None:
    """Return the nominal subject boundary of a simple affirmative change clause."""
    index = next((i for i, token in enumerate(tokens) if token.tag not in NOUN_TAGS), 0)
    if not index or len(tokens) < index + 3:
        return None
    subject, verb, *ending = tokens[index:]
    if subject.tag != "JKS" or verb.tag != "VV" or verb.form not in CHANGE_VERBS:
        return None
    if ending[-1].tag != "EF" or any(token.tag != "EP" for token in ending[:-1]):
        return None
    return subject.start


def is_perception(tokens: list[Token]) -> bool:
    forms = [(token.form, token.tag) for token in tokens]
    return (
        ("보", "VV") in forms
        or ("보이", "VV") in forms
        or any(
            left == ("목격", "NNG") and right == ("하", "XSV") for left, right in pairwise(forms)
        )
    )


def source_role(pair: FixedPair, occurrence: str, kiwi: Kiwi) -> DirectSource | None:
    """Prefer a proven change subject and veto observation-only locatives."""
    fallback = explicit_source(pair, occurrence, kiwi)
    if occurrence != "observed":
        return None
    event, candidate = pair.event, pair.candidate
    index, start, end = event["clause_index"], event["start"], event["end"]
    if any(SOURCE_UNKNOWN.search(clause) for clause in pair.clauses[index:]):
        return None
    tokens = kiwi.tokenize(event["quote"])
    if is_perception(tokens):
        return None
    subject_end = changed_subject_end(tokens)
    if subject_end is None:
        return fallback
    complete_event = pair.clauses[index - 1][end:] in {"", ".", "。"}
    if (
        complete_event
        and candidate.clause_index == index
        and candidate.start == start
        and candidate.end == start + subject_end
    ):
        return DirectSource(index, candidate.start, candidate.end, start, end)
    return None
