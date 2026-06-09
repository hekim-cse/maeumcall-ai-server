from __future__ import annotations

from llm.huggingface_provider import complete_hf_messages


def complete_professor_appointment_ai_message(prompt: str) -> str:
    """
    교수님 면담 예약 응답 생성을 위한 LLM 호출 래퍼이다.
    """
    return complete_hf_messages(
        [
            {
                "role": "system",
                "content": (
                    "너는 대학 교수님 역할이다. "
                    "학생의 면담 예약 요청에 대해 공손하지만 약간 딱딱한 말투로 짧게 응답한다."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]
    )
