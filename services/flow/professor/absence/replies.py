from __future__ import annotations


def get_professor_absence_recommended_replies(conversation_state: str) -> list[str]:
    """
    교수님 결석 사유 전달 상태별 추천 답변을 반환한다.
    """
    if conversation_state == "collecting_absence_info":
        return [
            "자료구조 수업입니다.",
            "오늘 수업에 결석하게 되어 연락드렸습니다.",
            "몸이 좋지 않아 병원에 가게 되었습니다.",
        ]

    if conversation_state == "confirming_absence_info":
        return [
            "네, 맞습니다.",
            "수업명을 수정하고 싶습니다.",
            "결석 날짜를 수정하고 싶습니다.",
        ]

    if conversation_state == "absence_noted":
        return [
            "네, 감사합니다.",
            "확인했습니다.",
        ]

    if conversation_state == "closing":
        return [
            "네, 감사합니다.",
        ]

    return [
        "자료구조 수업입니다.",
        "오늘 수업에 결석하게 되어 연락드렸습니다.",
        "몸이 좋지 않아 병원에 가게 되었습니다.",
    ]
