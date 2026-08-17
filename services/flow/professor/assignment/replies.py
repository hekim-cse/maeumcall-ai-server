from __future__ import annotations


def get_professor_assignment_recommended_replies(conversation_state: str) -> list[str]:
    """
    교수님 과제 문의 상태별 추천 답변을 반환한다.
    """
    if conversation_state == "collecting_assignment_info":
        return [
            "자료구조 수업 과제입니다.",
            "과제 제출 형식을 여쭤보고 싶습니다.",
            "김개굴 학생입니다.",
        ]

    if conversation_state == "answering_assignment_question":
        return [
            "네, 알겠습니다.",
            "추가로 하나 더 여쭤봐도 될까요?",
            "감사합니다.",
        ]

    if conversation_state == "closing":
        return [
            "네, 감사합니다.",
        ]

    return [
        "자료구조 수업 과제입니다.",
        "과제 제출 형식을 여쭤보고 싶습니다.",
        "김개굴 학생입니다.",
    ]
