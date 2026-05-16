from __future__ import annotations

from typing import List


RECOMMENDED_REPLIES = {
    "greeting": [
        "진료 예약을 하고 싶습니다.",
        "예약 가능한 시간을 문의하고 싶습니다.",
        "처음 방문인데 예약이 가능할까요?",
    ],
    "asking_purpose": [
        "진료 예약을 하고 싶습니다.",
        "예약 시간을 변경하고 싶습니다.",
        "예약 관련해서 문의드리고 싶습니다.",
    ],
    "asking_department": [
        "내과 진료를 예약하고 싶습니다.",
        "피부과 진료를 예약하고 싶습니다.",
        "어느 과로 가야 할지 상담받고 싶습니다.",
    ],
    "asking_date": [
        "내일로 예약하고 싶습니다.",
        "이번 주 금요일에 가능할까요?",
        "가능한 가장 빠른 날짜로 예약하고 싶습니다.",
    ],
    "asking_time": [
        "오후 3시쯤 가능할까요?",
        "가능한 오후 시간대를 알려주세요.",
        "가장 빠른 오후 시간으로 예약하고 싶습니다.",
    ],
    "confirming_info": [
        "네, 맞습니다.",
        "시간을 다시 확인하고 싶습니다.",
        "연락처를 다시 말씀드릴게요.",
    ],
    "closing": [
        "네, 감사합니다.",
        "확인했습니다. 감사합니다.",
        "수고하세요.",
    ],
    "END": [],
}


def get_recommended_replies(conversation_state: str) -> List[str]:
    return RECOMMENDED_REPLIES.get(conversation_state, [])