from __future__ import annotations

import re
from typing import Dict, Optional


def extract_restaurant_reservation_info(text: str) -> Dict[str, Optional[str]]:
    """
    식당 예약 발화에서 날짜, 시간, 인원 정보를 추출한다.

    현재 MVP에서는 복잡한 자연어 처리를 하지 않고,
    자주 나오는 예약 표현을 규칙 기반으로 처리한다.
    """
    text = (text or "").strip()

    return {
        "intent": _extract_intent(text),
        "date": _extract_date(text),
        "time": _extract_time(text),
        "party_size": _extract_party_size(text),
        "user_name": _extract_user_name(text),
    }


def _extract_intent(text: str) -> Optional[str]:
    if any(keyword in text for keyword in ["예약", "자리", "방문"]):
        return "reservation"

    return None


def _extract_date(text: str) -> Optional[str]:
    date_keywords = [
        "오늘",
        "내일",
        "모레",
        "이번 주말",
        "주말",
        "이번 토요일",
        "이번 일요일",
        "토요일",
        "일요일",
        "평일",
    ]

    for keyword in date_keywords:
        if keyword in text:
            return keyword

    # 6월 10일, 6/10 같은 표현
    match = re.search(r"(\d{1,2})월\s*(\d{1,2})일", text)
    if match:
        return f"{match.group(1)}월 {match.group(2)}일"

    match = re.search(r"(\d{1,2})/(\d{1,2})", text)
    if match:
        return f"{match.group(1)}월 {match.group(2)}일"

    return None


def _extract_time(text: str) -> Optional[str]:
    # 저녁 7시, 오후 6시 반, 7시, 19시 등
    match = re.search(r"(오전|오후|저녁|낮|밤)?\s*(\d{1,2})시\s*(반)?", text)
    if match:
        period = match.group(1) or ""
        hour = match.group(2)
        half = " 반" if match.group(3) else ""

        if period:
            return f"{period} {hour}시{half}"

        return f"{hour}시{half}"

    # 가장 빠른 시간
    if "가장 빠른" in text or "제일 빠른" in text:
        return "가장 빠른 시간"

    return None


def _extract_party_size(text: str) -> Optional[str]:
    korean_number_map = {
        "한": "1",
        "두": "2",
        "세": "3",
        "네": "4",
        "다섯": "5",
        "여섯": "6",
        "일곱": "7",
        "여덟": "8",
        "아홉": "9",
        "열": "10",
    }

    # 2명, 4명, 6명
    match = re.search(r"(\d{1,2})\s*(명|분|인)", text)
    if match:
        return f"{match.group(1)}명"

    # 두 명, 네 명, 여섯 명
    for korean, number in korean_number_map.items():
        if re.search(fr"{korean}\s*(명|분|인)", text):
            return f"{number}명"

    return None


def _extract_user_name(text: str) -> Optional[str]:
    """
    식당 예약자 이름을 추출한다.

    예:
    - 김개굴 이름으로 예약해주세요.
    - 예약자는 김개굴입니다.
    - 김개굴로 예약할게요.
    - 이름은 김개굴입니다.
    """
    patterns = [
        # 예약자는 홍길동입니다 / 예약자는 홍길동이에요
        r"예약자는\s*([가-힣]{2,5})\s*(?:입니다|이에요|예요|입니다\.|이에요\.|예요\.)",

        # 이름은 홍길동입니다 / 이름은 홍길동이에요
        r"이름은\s*([가-힣]{2,5})\s*(?:입니다|이에요|예요|입니다\.|이에요\.|예요\.)",

        # 김개굴 이름으로 / 김개굴 성함으로
        r"([가-힣]{2,5})\s*이름으로",
        r"([가-힣]{2,5})\s*성함으로",

        # 김개굴로 예약 / 김개굴으로 예약
        r"([가-힣]{2,5})\s*으로\s*예약",
        r"([가-힣]{2,5})\s*로\s*예약",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    return None
