from __future__ import annotations

from llm.huggingface_provider import complete_hf_messages


def complete_professor_assignment_ai_message(prompt: str) -> str:
    """
    교수님 과제 문의 응답 생성을 위한 LLM 호출 래퍼이다.
    """
    return complete_hf_messages(
        [
            {
                "role": "system",
                "content": (
                    "너는 대학 교수님 역할이다. "
                    "학생의 과제 문의에 대해 공손하지만 약간 딱딱한 말투로 짧게 응답한다."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]
    )
