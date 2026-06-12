from __future__ import annotations

from typing import Iterable


DEFAULT_CASUAL_BLOCKLIST = [
    "ㅋㅋ",
    "ㅎㅎ",
    "응",
    "그래",
    "오케이",
    "넵",
    "좋아",
    "말해줘",
    "괜찮아",
    "그때 보자",
    "알아서 해",
]


def has_too_casual_tone(
    text: str,
    extra_blocklist: Iterable[str] | None = None,
) -> bool:
    """
    전화 시뮬레이션 응답에서 지나치게 가벼운 표현이 포함되어 있는지 확인한다.

    기본적으로 공손한 전화 응답에 어울리지 않는 표현을 차단한다.
    시나리오별로 추가 차단어가 필요하면 extra_blocklist로 확장할 수 있다.
    """
    normalized = text or ""

    blocklist = list(DEFAULT_CASUAL_BLOCKLIST)

    if extra_blocklist:
        blocklist.extend(extra_blocklist)

    return any(word in normalized for word in blocklist)
