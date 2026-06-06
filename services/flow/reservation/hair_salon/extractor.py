from __future__ import annotations

import re
from typing import Dict, Optional


def extract_hair_salon_reservation_info(text: str) -> Dict[str, Optional[str]]:
    """
    미용실 예약 발화에서 날짜, 시간, 시술 종류, 디자이너, 예약자 이름을 추출한다.
    """
    text = (text or "").strip()

    return {
        "intent": _extract_intent(text),
        "date": _extract_date(text),
        "time": _extract_time(text),
        "service_type": _extract_service_type(text),
        "designer": _extract_designer(text),
        "user_name": _extract_user_name(text),
    }


def _extract_intent(text: str) -> Optional[str]:
    if any(keyword in text for keyword in ["예약", "가능", "시술", "커트", "펌", "염색", "방문"]):
        return "reservation"

    return None


def _extract_date(text: str) -> Optional[str]:
    date_keywords = [
        "오늘",
        "내일",
        "모레",
        "이번 주말",
        "주말",
        "다음 주",
        "다음주",
    ]

    for keyword in date_keywords:
        if keyword in text:
            return keyword

    match = re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", text)
    if match:
        return f"{match.group(1)}월 {match.group(2)}일"

    match = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})", text)
    if match:
        return f"{match.group(1)}월 {match.group(2)}일"

    return None


def _extract_time(text: str) -> Optional[str]:
    period = None

    if "오전" in text:
        period = "오전"
    elif "오후" in text:
        period = "오후"
    elif "저녁" in text:
        period = "저녁"

    match = re.search(r"(\d{1,2})\s*시\s*(반)?", text)
    if match:
        hour = match.group(1)
        half = " 반" if match.group(2) else ""

        if period:
            return f"{period} {hour}시{half}"

        return f"{hour}시{half}"

    if "가장 빠른" in text or "제일 빠른" in text:
        return "가장 빠른 시간"

    return None


def _extract_service_type(text: str) -> Optional[str]:
    service_keywords = [
        "볼륨매직",
        "다운펌",
        "커트",
        "컷",
        "펌",
        "파마",
        "염색",
        "탈색",
        "클리닉",
        "드라이",
        "매직",
        "앞머리",
    ]

    for keyword in service_keywords:
        if keyword in text:
            if keyword == "컷":
                return "커트"
            if keyword == "파마":
                return "펌"
            return keyword

    return None


def _extract_designer(text: str) -> Optional[str]:
    """
    미용실 디자이너 이름을 추출한다.

    예:
    - 수진 디자이너님으로 예약하고 싶어요.
    - 민지 선생님 가능한가요?
    - 디자이너는 지우 선생님으로 부탁드려요.
    - 아무 선생님이나 괜찮아요.
    """
    if any(keyword in text for keyword in ["아무나", "아무 선생님", "가능한 선생님", "상관없"]):
        return "가능한 디자이너"

    patterns = [
        r"디자이너는\s*([가-힣]{2,5})",
        r"([가-힣]{2,5})\s*디자이너",
        r"([가-힣]{2,5})\s*선생님",
        r"([가-힣]{2,5})\s*원장님",
        r"([가-힣]{2,5})\s*실장님",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    return None


def _extract_user_name(text: str) -> Optional[str]:
    """
    미용실 예약자 이름을 추출한다.
    """
    patterns = [
        r"예약자는\s*([가-힣]{2,5})\s*(?:입니다|이에요|예요|입니다\.|이에요\.|예요\.)",
        r"이름은\s*([가-힣]{2,5})\s*(?:입니다|이에요|예요|입니다\.|이에요\.|예요\.)",
        r"([가-힣]{2,5})\s*이름으로",
        r"([가-힣]{2,5})\s*성함으로",
        r"([가-힣]{2,5})\s*으로\s*예약",
        r"([가-힣]{2,5})\s*로\s*예약",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    return None
