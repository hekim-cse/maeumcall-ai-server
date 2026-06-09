from __future__ import annotations

import re
from typing import Dict, Optional


def extract_professor_appointment_info(text: str) -> Dict[str, Optional[str]]:
    """
    교수님 면담 예약 발화에서 필요한 정보를 추출한다.

    추출 대상:
    - appointment_purpose: 면담 목적
    - date: 면담 희망 날짜
    - time: 면담 희망 시간
    - user_name: 학생 이름
    """
    normalized = _normalize(text)

    return {
        "intent": "appointment_booking",
        "appointment_purpose": _extract_purpose(normalized),
        "date": _extract_date(normalized),
        "time": _extract_time(normalized),
        "user_name": _extract_user_name(normalized),
    }


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _extract_purpose(text: str) -> Optional[str]:
    purpose_keywords = [
        "진로 상담",
        "진로",
        "과제",
        "성적",
        "수업",
        "연구실",
        "졸업",
        "상담",
        "프로젝트",
        "발표",
        "출석",
    ]

    for keyword in purpose_keywords:
        if keyword in text:
            if keyword == "진로":
                return "진로 상담"
            if keyword == "상담":
                return "상담"
            return keyword

    if "면담" in text:
        return "면담"

    return None


def _extract_date(text: str) -> Optional[str]:
    date_patterns = [
        r"이번 주\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)",
        r"다음 주\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)",
        r"(오늘|내일|모레)",
        r"(월요일|화요일|수요일|목요일|금요일|토요일|일요일)",
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0).strip()

    return None


def _extract_time(text: str) -> Optional[str]:
    time_patterns = [
        r"(오전|오후)\s*\d{1,2}\s*시\s*\d{1,2}\s*분",
        r"(오전|오후)\s*\d{1,2}\s*시",
        r"\d{1,2}\s*시\s*\d{1,2}\s*분",
        r"\d{1,2}\s*시",
    ]

    for pattern in time_patterns:
        match = re.search(pattern, text)
        if match:
            return _normalize_time(match.group(0))

    korean_time_map = {
        "한 시": "1시",
        "두 시": "2시",
        "세 시": "3시",
        "네 시": "4시",
        "다섯 시": "5시",
        "여섯 시": "6시",
        "일곱 시": "7시",
        "여덟 시": "8시",
        "아홉 시": "9시",
        "열 시": "10시",
        "열한 시": "11시",
        "열두 시": "12시",
    }

    for source, target in korean_time_map.items():
        if source in text:
            prefix = ""
            if "오전" in text:
                prefix = "오전 "
            elif "오후" in text:
                prefix = "오후 "
            return f"{prefix}{target}".strip()

    return None


def _normalize_time(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip())
    value = re.sub(r"(\d{1,2})\s*시", r"\1시", value)
    value = re.sub(r"(\d{1,2})\s*분", r"\1분", value)
    return value


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
        "면담",
        "예약",
        "가능",
        "관련",
        "상담",
        "과제",
        "진로",
        "수업",
        "오늘",
        "내일",
        "모레",
    }

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip()
            if name not in blocked:
                return name

    return None
