from __future__ import annotations

import re
from typing import Dict, Optional


def extract_professor_absence_info(text: str) -> Dict[str, Optional[str]]:
    """
    교수님 결석 사유 전달 발화에서 필요한 정보를 추출한다.

    추출 대상:
    - class_name: 수업명
    - absence_date: 결석 날짜
    - absence_reason: 결석 사유
    - user_name: 학생 이름
    """
    normalized = _normalize(text)

    return {
        "intent": "absence_notice",
        "class_name": _extract_class_name(normalized),
        "absence_date": _extract_absence_date(normalized),
        "absence_reason": _extract_absence_reason(normalized),
        "user_name": _extract_user_name(normalized),
    }


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _extract_class_name(text: str) -> Optional[str]:
    patterns = [
        r"([가-힣A-Za-z0-9\s]{2,20})\s*수업",
        r"([가-힣A-Za-z0-9\s]{2,20})\s*강의",
        r"([가-힣A-Za-z0-9\s]{2,20})\s*과목",
    ]

    blocked = {
        "오늘",
        "내일",
        "이번",
        "다음",
        "교수님",
        "결석",
        "사유",
        "수업",
        "강의",
        "과목",
    }

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip()
            name = re.sub(r"^(오늘|내일|이번 주|다음 주)\s*", "", name).strip()
            if name and name not in blocked:
                return name

    return None


def _extract_absence_date(text: str) -> Optional[str]:
    date_patterns = [
        r"오늘",
        r"내일",
        r"모레",
        r"이번 주\s*[월화수목금토일]요일",
        r"다음 주\s*[월화수목금토일]요일",
        r"[월화수목금토일]요일",
        r"\d{1,2}월\s*\d{1,2}일",
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            return _normalize_date(match.group(0))

    return None


def _normalize_date(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip())
    value = re.sub(r"(\d{1,2})월\s*(\d{1,2})일", r"\1월 \2일", value)
    return value


def _extract_absence_reason(text: str) -> Optional[str]:
    reason_keywords = [
        ("몸이 좋지", "몸이 좋지 않음"),
        ("아파", "몸이 아픔"),
        ("병원", "병원 방문"),
        ("감기", "감기 증상"),
        ("독감", "독감 증상"),
        ("장염", "장염 증상"),
        ("개인 사정", "개인 사정"),
        ("가족", "가족 사정"),
        ("교통", "교통 문제"),
        ("지각", "지각"),
        ("면접", "면접 일정"),
    ]

    for keyword, reason in reason_keywords:
        if keyword in text:
            return reason

    if "결석" in text and "사유" in text:
        return None

    return None


def _extract_user_name(text: str) -> Optional[str]:
    patterns = [
        r"([가-힣]{2,4})\s*학생입니다",
        r"([가-힣]{2,4})\s*입니다",
        r"([가-힣]{2,4})\s*이라고 합니다",
        r"([가-힣]{2,4})\s*라고 합니다",
        r"([가-힣]{2,4})\s*이름으로",
    ]

    blocked = {
        "교수님",
        "결석",
        "사유",
        "수업",
        "강의",
        "과목",
        "오늘",
        "내일",
        "모레",
        "병원",
        "가족",
        "개인",
    }

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip()
            if name not in blocked:
                return name

    return None
