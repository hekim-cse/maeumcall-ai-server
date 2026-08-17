from __future__ import annotations

import asyncio
from typing import Any

from llm.client import complete_json_messages
from llm.structured_output import allowed_string, complete_validated_json, optional_string
from schemas.chat_models import ChatMessage

CATEGORY_TONE_POLICY: dict[str, str] = {
    "교수님": "존댓말을 사용하고 목적·일정·요청을 정중하고 명확하게 표현한다.",
    "가족": "원문의 반말 또는 존댓말을 유지하며 따뜻하고 배려 있게 표현한다.",
    "친구": "원문의 말투를 유지하며 친근하되 무례한 표현은 사용하지 않는다.",
    "연인": "원문의 친밀한 말투를 유지하면서 감정과 요청을 공격적이지 않게 분명히 표현한다.",
    "회사": "격식 있는 존댓말로 핵심, 근거, 일정 순서로 간결하게 표현한다.",
    "예약": "날짜, 시간, 인원과 요청 사항을 빠짐없이 정중하게 표현한다.",
    "고객센터": "문제 현상, 발생 시점, 요청 사항을 정중하고 명확하게 표현한다.",
    "시청": "문의 대상, 필요한 정보, 후속 질문을 행정 업무에 맞는 존댓말로 표현한다.",
    "배달": "주문 문제와 원하는 처리 방법을 정중하고 구체적으로 표현한다.",
    "일반": "원문의 말투와 의미를 유지하며 명확하고 자연스럽게 표현한다.",
}

ALLOWED_TAGS = {"정중함", "명확성", "간결성", "문법", "자연스러움"}


def _build_rewrite_messages(text: str, category: str) -> list[dict[str, str]]:
    policy = CATEGORY_TONE_POLICY[category]
    return [
        {
            "role": "system",
            "content": (
                "너는 한국어 통화 문장 교정기이다. 반드시 JSON 객체 하나만 출력한다. "
                "원문의 의미, 말투(반말/존댓말), 이모지, 줄바꿈을 보존한다. "
                "취향에 따른 문장부호나 띄어쓰기만 바꾸지 않는다. 변경할 필요가 없으면 changed=false로 응답한다. "
                f"이 카테고리의 표현 정책: {policy}"
            ),
        },
        {
            "role": "user",
            "content": (
                "다음 계약으로 문장을 검토하세요.\n"
                '{"changed": boolean, "improved_text": string | null, '
                '"tags": ["정중함" | "명확성" | "간결성" | "문법" | "자연스러움"]}\n'
                "changed=false이면 improved_text는 null, tags는 빈 배열이어야 합니다.\n"
                f"검토할 문장: {text}"
            ),
        },
    ]


def _validate_rewrite_result(data: dict[str, Any]) -> dict[str, Any]:
    changed = data.get("changed")
    if not isinstance(changed, bool):
        raise ValueError("changed must be a boolean")

    improved_text = optional_string(data, "improved_text")
    tags = data.get("tags")
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise ValueError("tags must be a string array")
    unique_tags = list(
        dict.fromkeys(allowed_string({"tag": tag}, "tag", ALLOWED_TAGS) for tag in tags)
    )

    if changed and not improved_text:
        raise ValueError("improved_text is required when changed is true")
    if not changed and (improved_text is not None or unique_tags):
        raise ValueError("unchanged output must contain null improved_text and empty tags")

    return {"changed": changed, "improved_text": improved_text, "tags": unique_tags}


def _rewrite_message(text: str, category: str) -> dict[str, Any]:
    return complete_validated_json(
        _build_rewrite_messages(text, category),
        completion=complete_json_messages,
        validator=_validate_rewrite_result,
        operation="message_correction",
    )


async def improve_messages(
    messages: list[ChatMessage],
    category: str | None,
) -> tuple[list[str | None], list[list[str] | None]]:
    selected_category = (category or "일반").strip()
    if selected_category not in CATEGORY_TONE_POLICY:
        raise ValueError(f"unsupported correction category: {selected_category}")

    improved: list[str | None] = [None] * len(messages)
    tags: list[list[str] | None] = [None] * len(messages)

    for index, message in enumerate(messages):
        text = (message.text or "").strip()
        if not text or message.role != "user":
            continue

        result = await asyncio.to_thread(_rewrite_message, text, selected_category)
        if result["changed"]:
            improved[index] = result["improved_text"]
            tags[index] = result["tags"]

    return improved, tags
