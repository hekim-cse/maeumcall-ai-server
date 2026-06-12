from __future__ import annotations

import re
from typing import Dict, Optional


def extract_professor_assignment_info(text: str) -> Dict[str, Optional[str]]:
    """
    교수님 과제 문의 발화에서 필요한 정보를 추출한다.

    추출 대상:
    - assignment_topic: 과제 주제/유형
    - question: 질문 내용
    - user_name: 학생 이름
    """
    normalized = _normalize(text)

    return {
        "intent": "assignment_inquiry",
        "assignment_topic": _extract_assignment_topic(normalized),
        "question": _extract_question(normalized),
        "user_name": _extract_user_name(normalized),
    }


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _extract_assignment_topic(text: str) -> Optional[str]:
    topic_keywords = [
        "제출 형식",
        "제출 방식",
        "제출 기한",
        "마감 기한",
        "보고서",
        "레포트",
        "발표",
        "팀플",
        "개인 과제",
        "과제",
        "PDF",
        "분량",
    ]

    for keyword in topic_keywords:
        if keyword in text:
            if keyword == "PDF":
                return "제출 형식"
            return keyword

    return None


def _extract_question(text: str) -> Optional[str]:
    question_keywords = [
        "여쭤보고 싶",
        "궁금",
        "확인하고 싶",
        "질문",
        "어떻게",
        "언제",
        "무엇",
        "몇",
        "가능",
        "되나요",
        "될까요",
        "인가요",
    ]

    if any(keyword in text for keyword in question_keywords):
        return text

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
        "과제",
        "문의",
        "제출",
        "형식",
        "기한",
        "보고서",
        "레포트",
        "발표",
        "팀플",
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
