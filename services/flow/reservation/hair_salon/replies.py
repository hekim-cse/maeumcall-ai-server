from __future__ import annotations

from typing import List


def get_hair_salon_recommended_replies(conversation_state: str) -> List[str]:
    """
    미용실 예약 상태별 추천 답변을 반환한다.
    """
    if conversation_state == "collecting_reservation_info":
        return [
            "내일 오후 3시에 커트 예약하고 싶습니다.",
            "가능한 디자이너 선생님으로 예약하고 싶습니다.",
            "예약자 이름은 김개굴입니다.",
        ]

    if conversation_state == "confirming_info":
        return [
            "네, 맞습니다.",
            "시간을 바꾸고 싶습니다.",
            "디자이너를 바꾸고 싶습니다.",
        ]

    if conversation_state == "checking_availability":
        return [
            "네, 기다리겠습니다.",
            "확인 부탁드립니다.",
        ]

    if conversation_state == "reservation_available":
        return [
            "네, 그 시간으로 예약해주세요.",
            "좋습니다. 예약해주세요.",
            "다른 시간도 가능할까요?",
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
        "미용실 예약하고 싶습니다.",
        "내일 커트 예약 가능할까요?",
    ]
