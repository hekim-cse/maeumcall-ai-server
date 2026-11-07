"""High-confidence A/S safety phrases that must bypass model-dependent routing."""

from __future__ import annotations

import re

from llm.errors import (
    AIProviderExecutionError,
    AIProviderUnavailableError,
    AIResponseValidationError,
)
from llm.huggingface_provider import complete_hf_safety_json
from llm.structured_output import complete_validated_json, require_exact_keys

SAFETY_CONFIRMATION_STATE = "confirming_safety_status"

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
        r"|올라옵니다|피어오릅니다|발생합니다|발생했어요|발생했습니다)"
    ),
    re.compile(
        r"타는\s*냄새(?:가|는)?\s*(?:나서|납니다|나요(?!\s*\?)|나네요|나고"
        r"|났어요|났습니다|올라옵니다|발생합니다|발생했어요|발생했습니다)"
    ),
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


_SAFETY_CONCERN_TERMS = (
    "연기",
    "연무",
    "불꽃",
    "스파크",
    "탄내",
    "타는",
    "매캐한 냄새",
    "부풀",
    "팽창",
    "뜨거",
    "뜨겁",
    "발열",
    "그을",
    "피복",
    "찌릿",
    "벌어",
    "볼록",
    "들뜬",
    "들떴",
    "녹아",
)

_SAFETY_FOCUS_PROMPT = (
    "너는 A/S 접수의 안전 위험만 판정한다. 사용자가 현재 A/S 대상 제품에서 "
    "실제로 발생했다고 말한 연기, 심한 발열, 타는 냄새, 배터리 변형, 불꽃, "
    "전선 피복 손상은 true다. 다른 사람·다른 제품의 경험, 후기, 가정, "
    "발생 여부 질문, 명시적 부정은 false다. JSON 객체 하나만 반환한다: "
    '{"current_safety_issue": true 또는 false}'
)


def has_safety_concern(user_message: str) -> bool:
    """Find a possible hazard worth asking about, without declaring one present."""
    return any(term in user_message for term in _SAFETY_CONCERN_TERMS)


def classify_safety_concern(user_message: str) -> bool | None:
    """Return a focused model decision, or None when it cannot be trusted."""
    try:
        return complete_validated_json(
            [
                {"role": "system", "content": _SAFETY_FOCUS_PROMPT},
                {"role": "user", "content": user_message},
            ],
            completion=complete_hf_safety_json,
            validator=_validate_safety_decision,
            operation="as_safety_confirmation",
        )
    except (AIProviderExecutionError, AIProviderUnavailableError, AIResponseValidationError):
        return None


def _validate_safety_decision(parsed: dict) -> bool:
    require_exact_keys(parsed, {"current_safety_issue"})
    decision = parsed["current_safety_issue"]
    if not isinstance(decision, bool):
        raise ValueError("current_safety_issue must be boolean")
    return decision


def safety_confirmation_reply(user_message: str) -> str:
    """Interpret only short explicit answers to the pending safety question."""
    answer = user_message.strip().rstrip(".!?。 ")
    if answer in {"네", "예", "맞아요", "맞습니다", "네, 맞아요", "네, 실제로 그렇습니다"}:
        return "confirmed"
    if answer in {"아니요", "아닙니다", "아니요, 그런 증상은 없습니다", "안전 이상은 없습니다"}:
        return "denied"
    if answer in {"통화를 마칠게요", "통화를 마치겠습니다", "그만할게요"}:
        return "closing"
    return "unclear"
