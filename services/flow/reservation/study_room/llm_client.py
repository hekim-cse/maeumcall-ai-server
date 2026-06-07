from __future__ import annotations

from llm.huggingface_provider import complete_hf_messages


def complete_study_room_ai_message(prompt: str) -> str:
    """
    스터디룸 예약 응답 생성을 위한 LLM 호출 래퍼이다.

    graph/nodes에서 LLM 구현체를 직접 호출하지 않도록 분리한다.
    """
    return complete_hf_messages(
        [
            {
                "role": "system",
                "content": "너는 스터디룸 예약 전화를 받는 직원이다. 자연스럽고 짧게 응답한다.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]
    )
