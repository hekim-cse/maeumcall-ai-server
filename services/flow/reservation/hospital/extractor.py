from __future__ import annotations

import re
from typing import Optional, Dict


DEPARTMENT_KEYWORDS = [
    "내과",
    "피부과",
    "정형외과",
    "외과",
    "이비인후과",
    "소아과",
    "치과",
    "안과",
    "산부인과",
    "신경과",
    "정신건강의학과",
]

DATE_KEYWORDS = [
    "오늘",
    "내일",
    "모레",
    "이번 주",
    "다음 주",
    "월요일",
    "화요일",
    "수요일",
    "목요일",
    "금요일",
    "토요일",
    "일요일",
]

RESERVATION_KEYWORDS = ["예약", "진료", "접수"]
CHANGE_KEYWORDS = ["변경", "바꾸", "시간 바꾸", "예약 변경"]
CANCEL_KEYWORDS = ["취소", "예약 취소"]


def extract_intent(text: str) -> Optional[str]:
    text = text or ""

    if any(word in text for word in CANCEL_KEYWORDS):
        return "cancel"

    if any(word in text for word in CHANGE_KEYWORDS):
        return "change"

    if any(word in text for word in RESERVATION_KEYWORDS):
        return "reservation"

    return None


def extract_department(text: str) -> Optional[str]:
    text = text or ""

    for department in DEPARTMENT_KEYWORDS:
        if department in text:
            return department

    return None


def extract_date(text: str) -> Optional[str]:
    text = text or ""

    for date in DATE_KEYWORDS:
        if date in text:
            return date

    date_pattern = r"\d{1,2}월\s?\d{1,2}일"
    match = re.search(date_pattern, text)
    if match:
        return match.group()

    return None


def extract_time(text: str) -> Optional[str]:
    text = text or ""

    time_pattern = r"(오전|오후)?\s?\d{1,2}시(?:\s?\d{1,2}분)?"
    match = re.search(time_pattern, text)
    if match:
        return match.group().strip()

    if "오전" in text:
        return "오전"

    if "오후" in text:
        return "오후"

    return None


def extract_hospital_reservation_info(text: str) -> Dict[str, Optional[str]]:
    return {
        "intent": extract_intent(text),
        "department": extract_department(text),
        "date": extract_date(text),
        "time": extract_time(text),
    }