from __future__ import annotations

from typing import List, Dict, Any

from llm.huggingface_provider import complete_hf_messages


def complete_hospital_ai_message(
    messages: List[Dict[str, Any]],
    *,
    temperature: float = 0.2,
    max_new_tokens: int = 120,
) -> str:
    """
    병원 예약 LangGraph에서 ai_message 생성을 위해 사용하는 LLM 호출 래퍼이다.

    graph.py 또는 nodes.py가 HuggingFace provider를 직접 의존하지 않도록 분리한다.
    이후 테스트에서는 이 함수만 monkeypatch하면 된다.
    """
    return complete_hf_messages(
        messages,
        temperature=temperature,
        max_new_tokens=max_new_tokens,
    )
