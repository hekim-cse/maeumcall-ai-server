"""High-confidence A/S safety phrases that must bypass model-dependent routing."""

from __future__ import annotations

import re

_EXPLICIT_SAFETY_PATTERNS = (
    re.compile(
        r"배터리(?:가|는|의)?\s*(?:(?:심하게|많이|점점)\s*)?"
        r"(?:부풀어\s*(?:올라(?!야|면)|올랐|있(?:어요|습니다))"
        r"|부풀었(?:어요|습니다|네요|다(?!면|는|고|며)|다고\s*(?:말씀|문의|신고))"
        r"|부풀었습니다|부풀고(?!\s*있(?:는지|으면))|부풀음"
        r"|팽창했(?:어요|습니다|네요|다(?!면)))"
    ),
    re.compile(
        r"연기(?:가|는)?\s*(?:나서|납니다|나요(?!\s*\?)|나네요|나고|났어요|났습니다"
        r"|올라옵니다|피어오릅니다|피어올랐어요|피어올랐습니다"
        r"|발생합니다|발생했어요|발생했습니다)"
    ),
    re.compile(
        r"(?:플러그|콘센트|충전기)[^.!?\n]{0,25}"
        r"불꽃(?:이|은)?\s*(?:튀었어요|튀었습니다|튀어올랐어요|튀네요)"
    ),
    re.compile(
        r"타는\s*냄새(?:가|는)?\s*(?:나서|납니다|나요(?!\s*\?)|나네요|나고"
        r"|났어요|났습니다|올라옵니다|발생합니다|발생했어요|발생했습니다)"
    ),
    re.compile(
        r"(?:탄내|매캐한\s*냄새)(?:가|는)?\s*"
        r"(?:올라와(?:서|요)?|올라옵니다|납니다|났어요|났습니다)"
    ),
    re.compile(
        r"(?:충전\s*거치대|충전대|충전기|전원\s*어댑터)[^.!?\n]{0,30}"
        r"연무(?:가|는)?\s*(?:올라왔어요|피어올라(?:서|요)?)"
    ),
    re.compile(
        r"배터리\s*(?:덮개|뚜껑|커버)(?:가|는)?[^.!?\n]{0,25}"
        r"(?:밀려\s*(?:나와|올라와)|벌어졌(?:어요|습니다))"
    ),
    re.compile(
        r"(?:기기|제품|본체|충전기|배터리|충전\s*케이블(?:\s*연결부|\s*단자)?"
        r"|전원\s*어댑터|충전\s*거치대|충전대)(?:가|는)?[^.!?\n]{0,35}"
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
