from __future__ import annotations


def get_professor_appointment_recommended_replies(conversation_state: str) -> list[str]:
    """
    교수님 면담 예약 상태별 추천 답변을 반환한다.
    """
    if conversation_state == "collecting_appointment_info":
        return [
            "진로 상담 관련해서 면담을 요청드리고 싶습니다.",
            "이번 주 수요일 오후에 면담 가능하실까요?",
            "김개굴 학생입니다.",
        ]

    if conversation_state == "confirming_info":
        return [
            "네, 맞습니다.",
            "시간을 변경하고 싶습니다.",
            "면담 목적을 다시 말씀드리겠습니다.",
        ]

    if conversation_state == "appointment_confirmed":
        return [
            "네, 감사합니다.",
            "확인했습니다.",
        ]

    if conversation_state == "closing":
        return [
            "네, 감사합니다.",
        ]

    return [
        "면담 예약하고 싶습니다.",
        "진로 상담 관련해서 여쭤보고 싶습니다.",
        "이번 주 수요일 오후에 가능하실까요?",
    ]
