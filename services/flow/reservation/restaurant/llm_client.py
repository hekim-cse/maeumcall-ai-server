from __future__ import annotations

from llm.huggingface_provider import complete_hf_messages


def complete_restaurant_ai_message(prompt: str) -> str:
    """
    식당 예약 응답 생성을 위한 LLM 호출 래퍼이다.

    graph/nodes에서 LLM 구현체를 직접 호출하지 않도록 분리한다.
    이후 모델 변경, timeout, provider 변경이 필요할 때 이 파일만 수정하면 된다.
    """
    return complete_hf_messages(
        [
            {
                "role": "system",
                "content": "너는 식당 예약 전화를 받는 직원이다. 자연스럽고 짧게 응답한다.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]
    )
