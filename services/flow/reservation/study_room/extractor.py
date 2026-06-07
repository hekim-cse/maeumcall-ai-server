from __future__ import annotations

import re
from typing import Dict, Optional


def extract_study_room_reservation_info(text: str) -> Dict[str, Optional[str]]:
    """
    스터디룸 예약 발화에서 예약에 필요한 정보를 추출한다.

    추출 대상:
    - intent
    - date
    - start_time
    - duration
    - party_size
    - user_name
    """
    text = (text or "").strip()

    return {
        "intent": _extract_intent(text),
        "date": _extract_date(text),
        "start_time": _extract_start_time(text),
        "duration": _extract_duration(text),
        "party_size": _extract_party_size(text),
        "user_name": _extract_user_name(text),
    }


def _extract_intent(text: str) -> Optional[str]:
    if any(keyword in text for keyword in ["예약", "이용", "사용", "자리"]):
        return "reservation"

    return None


def _extract_date(text: str) -> Optional[str]:
    date_patterns = [
        "오늘",
        "내일",
        "모레",
        "이번 주말",
        "주말",
        "다음 주",
    ]

    for pattern in date_patterns:
        if pattern in text:
            return pattern

    match = re.search(r"(\d{1,2})월\s*(\d{1,2})일", text)
    if match:
        return f"{match.group(1)}월 {match.group(2)}일"

    return None


def _extract_start_time(text: str) -> Optional[str]:
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
        "열한": "11",
        "열두": "12",
    }

    # 오후 2시 / 오전 10시 / 저녁 7시
    match = re.search(r"(오전|오후|저녁|밤)\s*(\d{1,2})\s*시", text)
    if match:
        return f"{match.group(1)} {match.group(2)}시"

    # 오후 두 시 / 오전 열 시
    for korean, number in korean_number_map.items():
        match = re.search(fr"(오전|오후|저녁|밤)\s*{korean}\s*시", text)
        if match:
            return f"{match.group(1)} {number}시"

    # 2시부터 / 10시부터
    match = re.search(r"(\d{1,2})\s*시", text)
    if match:
        return f"{match.group(1)}시"

    # 두 시부터 / 네 시부터
    for korean, number in korean_number_map.items():
        if re.search(fr"{korean}\s*시", text):
            return f"{number}시"

    return None


def _extract_duration(text: str) -> Optional[str]:
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

    # 2시간 / 3 시간
    match = re.search(r"(\d{1,2})\s*시간", text)
    if match:
        return f"{match.group(1)}시간"

    # 두 시간 / 세 시간
    for korean, number in korean_number_map.items():
        if re.search(fr"{korean}\s*시간", text):
            return f"{number}시간"

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

    # 4명 / 6인 / 2분
    match = re.search(r"(\d{1,2})\s*(명|분|인)", text)
    if match:
        return f"{match.group(1)}명"

    # 네 명 / 두 명 / 여섯 명
    for korean, number in korean_number_map.items():
        if re.search(fr"{korean}\s*(명|분|인)", text):
            return f"{number}명"

    return None


def _extract_user_name(text: str) -> Optional[str]:
    """
    스터디룸 예약자 이름을 추출한다.

    예:
    - 김개굴 이름으로 예약해주세요.
    - 예약자는 김개굴입니다.
    - 김개굴로 예약할게요.
    - 이름은 김개굴입니다.
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
