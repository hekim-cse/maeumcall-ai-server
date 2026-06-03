from __future__ import annotations

from typing import List


def get_restaurant_recommended_replies(conversation_state: str) -> List[str]:
    """
    식당 예약 상태별 추천 답변을 반환한다.
    사용자가 다음 단계에서 말해볼 수 있는 문장 중심으로 구성한다.
    """
    if conversation_state == "asking_date":
        return [
            "오늘 저녁으로 예약하고 싶습니다.",
            "내일 저녁으로 예약하고 싶습니다.",
            "이번 주말로 예약하고 싶습니다.",
        ]

    if conversation_state == "asking_time":
        return [
            "저녁 7시로 예약하고 싶습니다.",
            "오후 6시 반쯤 가능할까요?",
            "가장 빠른 시간으로 예약하고 싶습니다.",
        ]

    if conversation_state == "asking_party_size":
        return [
            "두 명입니다.",
            "네 명입니다.",
            "여섯 명 예약하고 싶습니다.",
        ]

    if conversation_state == "confirming_info":
        return [
            "네, 맞습니다.",
            "시간을 바꾸고 싶습니다.",
            "날짜를 다시 정하고 싶습니다.",
        ]

    if conversation_state == "checking_availability":
        return [
            "네, 기다리겠습니다.",
            "확인 부탁드립니다.",
        ]

    if conversation_state == "reservation_available":
        return [
            "네, 그 시간으로 예약하겠습니다.",
            "좋습니다. 예약해주세요.",
            "그 시간 괜찮습니다.",
        ]

    if conversation_state == "reservation_unavailable":
        return [
            "다른 시간으로 가능할까요?",
            "가장 빠른 시간으로 알려주세요.",
            "다른 날짜로 확인해주세요.",
        ]

    if conversation_state == "reservation_confirmed":
        return [
            "네, 감사합니다.",
            "확인했습니다.",
        ]

    if conversation_state == "closing":
        return [
            "네, 감사합니다.",
            "괜찮습니다.",
        ]

    return [
        "예약하고 싶습니다.",
        "오늘 저녁 예약 가능할까요?",
    ]
