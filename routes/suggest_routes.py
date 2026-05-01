# routes/suggest_routes.py
from __future__ import annotations
from fastapi import APIRouter
from typing import List
import re, json

from llm.client import call_gpt          # ⬅️ 여기로 변경
from schemas.chat_models import (
    SuggestRequest, SuggestResponse,
    ImproveRequest, ImproveResponse,
)
from services.correction_service import improve_messages

router = APIRouter(prefix="/chat", tags=["chat-improve"])
router_compat = APIRouter(prefix="", tags=["chat-improve-compat"])  # 현행 그대로면 무시

def _suggest_prompt(req: SuggestRequest) -> str:
    cat = (req.category or "").strip()

    if cat in {"회사"}:
        style = """
- 말투: **격식/존댓말**, 간결·명료. 사적 대화 금지(날씨/안부 등 X).
- 내용: 상대 질문/요구에 **즉답**하거나 필요한 **구체 정보(수치·날짜·근거)**를 제시.
- 필요 시 **다음 액션/대안 1가지**를 제안(예: 제출 시각, 보완 항목, 회의 슬롯 제안).
- 각 항목은 **한 개의 완결된 응답**이며 문장 길이 제한 없음(1문장 이상 가능).
- 출력은 **JSON 배열(정확히 3개 문자열)**만: ["응답1","응답2","응답3"]
""".strip()
    if cat in {"교수님"}:
        style = """
- 말투: **격식/존댓말**, 간결·명료. 사적 대화 금지(날씨/안부 등 X).
- 교수님께 문의드리는 상황. 최대한 **정중하게**.
- 각 항목은 **한 개의 완결된 응답**이며 문장 길이 제한 없음(1문장 이상 가능).
- 출력은 **JSON 배열(정확히 3개 문자열)**만: ["응답1","응답2","응답3"]
""".strip()
    else:
        style = """
- 출력은 **JSON 배열(정확히 3개 문자열)**만: ["문장1","문장2","문장3"]
""".strip()

    return f"""다음 대화 문맥에서 **사용자**가 말할 수 있는 한국어 답변 3가지를 제안해줘.

{style}

[카테고리] {req.category}
[제목] {req.title}
[직전 상대역 발화]
{req.lastAgentUtterance}
""".strip()

def _parse_suggestions(raw: str) -> List[str]:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except Exception:
        pass
    return ["네 그렇게 하자", "조금만 더 알려줘", "시간 괜찮아?"]

@router.post("/suggest", response_model=SuggestResponse)
def suggest(req: SuggestRequest):
    raw = call_gpt(_suggest_prompt(req), timeout_s=8) or "[]"
    items = _parse_suggestions(raw)
    return SuggestResponse(suggestions=(items[:3] or [
        "좋아, 그럼 그렇게 할게", "좀 더 자세히 말해줘", "언제 시간이 돼?"
    ]))

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