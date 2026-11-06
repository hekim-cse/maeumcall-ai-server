"""High-confidence A/S safety phrases that must bypass model-dependent routing."""

from __future__ import annotations

import re

_EXPLICIT_SAFETY_PATTERNS = (
    re.compile(
        r"배터리(?:가|는|의)?[^.!?\n]{0,30}"
        r"(?:부풀어\s*(?:올라|올랐|있(?:어요|습니다))|부풀었(?:어요|습니다|네요|다)"
        r"|부풀었습니다|부풀고(?!\s*있는지)|부풀음|팽창했(?:어요|습니다|네요|다))"
    ),
    re.compile(r"연기(?:가|는)?\s*(?:나(?!지|는지|면|ㄹ)|납|났|올라|피어|보여|보입|발생했)"),
    re.compile(r"타는\s*냄새(?:가|는)?\s*(?:나(?!지|는지|면|ㄹ)|납|났|올라|발생했)"),
    re.compile(
        r"(?:기기|제품|본체|충전기|배터리)(?:가|는)?[^.!?\n]{0,25}"
        r"(?:뜨거워(?:집니다|졌어요|져요|요|서)|뜨겁습니다)"
    ),
)


def has_explicit_safety_issue(user_message: str) -> bool:
    """Return true only for supported affirmative hazard statements.

    This deliberately does not try to interpret every possible paraphrase. The
    model remains responsible for other wording; this guard covers explicit
    high-risk statements even when structured extraction fails.
    """
    return any(pattern.search(user_message) for pattern in _EXPLICIT_SAFETY_PATTERNS)
