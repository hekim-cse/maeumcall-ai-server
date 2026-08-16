# routes/suggest_routes.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from typing import Any, Dict, List

from llm.client import complete_json_messages
from llm.structured_output import complete_validated_json
from schemas.chat_models import (
    SuggestRequest, SuggestResponse,
    ImproveRequest, ImproveResponse,
)
from services.correction_service import improve_messages
from services.flow.common.scenario_keys import canonicalize_scenario_label
from services.prompt_registry import is_registered_prompt

router = APIRouter(prefix="/chat", tags=["chat-improve"])
router_compat = APIRouter(prefix="", tags=["chat-improve-compat"])

def _suggest_prompt(req: SuggestRequest) -> str:
    cat = canonicalize_scenario_label(req.category)

    if cat in {"회사"}:
        style = """
- 말투: **격식/존댓말**, 간결·명료. 사적 대화 금지(날씨/안부 등 X).
- 내용: 상대 질문/요구에 **즉답**하거나 필요한 **구체 정보(수치·날짜·근거)**를 제시.
- 필요 시 **다음 액션/대안 1가지**를 제안(예: 제출 시각, 보완 항목, 회의 슬롯 제안).
- 각 항목은 **한 개의 완결된 응답**이며 문장 길이 제한 없음(1문장 이상 가능).
- 출력은 **JSON 객체**만: {"suggestions": ["응답1","응답2","응답3"]}
""".strip()
    elif cat in {"교수님"}:
        style = """
- 말투: **격식/존댓말**, 간결·명료. 사적 대화 금지(날씨/안부 등 X).
- 교수님께 문의드리는 상황. 최대한 **정중하게**.
- 각 항목은 **한 개의 완결된 응답**이며 문장 길이 제한 없음(1문장 이상 가능).
- 출력은 **JSON 객체**만: {"suggestions": ["응답1","응답2","응답3"]}
""".strip()
    else:
        style = """
- 출력은 **JSON 객체**만: {"suggestions": ["문장1","문장2","문장3"]}
""".strip()

    return f"""다음 대화 문맥에서 **사용자**가 말할 수 있는 한국어 답변 3가지를 제안해줘.

{style}

[카테고리] {req.category}
[제목] {req.title}
[직전 상대역 발화]
{req.lastAgentUtterance}
""".strip()

def _validate_suggestions(data: Dict[str, Any]) -> List[str]:
    values = data.get("suggestions")
    if not isinstance(values, list) or len(values) != 3:
        raise ValueError("suggestions must contain exactly three items")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError("each suggestion must be a non-empty string")
    normalized = [value.strip() for value in values]
    if len(set(normalized)) != 3:
        raise ValueError("suggestions must be unique")
    return normalized

@router.post("/suggest", response_model=SuggestResponse)
def suggest(req: SuggestRequest):
    if not is_registered_prompt(req.category, req.title):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "UNSUPPORTED_SCENARIO",
                "message": "등록되지 않은 카테고리와 제목 조합입니다.",
            },
        )
    items = complete_validated_json(
        [{"role": "user", "content": _suggest_prompt(req)}],
        completion=lambda messages: complete_json_messages(messages, timeout_s=8),
        validator=_validate_suggestions,
    )
    return SuggestResponse(suggestions=items)

@router.post("/improve", response_model=ImproveResponse)
async def improve(req: ImproveRequest):
    improved, tags = await improve_messages(req.messages, req.category)
    return ImproveResponse(improved=improved, tags=tags)

# 호환 엔드포인트
@router_compat.post("/suggest", response_model=SuggestResponse)
def suggest_compat(req: SuggestRequest):
    return suggest(req)

@router_compat.post("/improve", response_model=ImproveResponse)
async def improve_compat(req: ImproveRequest):
    return await improve(req)
