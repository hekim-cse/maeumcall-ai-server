# routes/chat_routes.py
from __future__ import annotations
from fastapi import APIRouter
import os
from typing import Optional, List, Dict, Any

from schemas.chat_models import ChatRequest, ChatResponse
from services.chat_service import complete
from llm.postprocessor import strip_labels, demote_question_if_repeated
from llm.postprocessor import strip_smalltalk_for_strict_categories
from services.closing import is_closing_utterance, closing_line
from llm.prompt_builder import generate_prompts
from services.etiquette import maybe_get_etiquette_tip

from services.flow.reservation.router import complete_reservation_graph_if_supported

router = APIRouter(prefix="/chat", tags=["chat"])
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "8"))

def _fallback_reply(category: Optional[str]) -> str:
    base = (category or "").strip()
    if base == "가족": return "그래~ 잘 지내고 있지? 요즘 건강은 어때?"
    if base == "친구": return "ㅋㅋ 오랜만이네. 요즘 뭐 하고 지내?"
    if base == "연인": return "응, 오늘 하루 어땠어? 많이 피곤하지는 않아?"
    if base == "회사": return "확인했습니다. 일정 관련해서 추가로 공유드릴까요?"
    if base == "교수님": return "네, 질문 감사합니다. 그 부분에 대해 설명드리죠."
    if base == "예약": return "안녕하세요, 예약 도와드리겠습니다. 어떤 일정으로 하실까요?"
    if base == "고객센터": return "불편을 드려 죄송합니다. 어떤 문제인지 조금만 더 알려주실 수 있을까요?"
    if base == "시청": return "안내드리겠습니다. 어떤 민원 관련 문의이신가요?"
    if base == "배달": return "확인 도와드리겠습니다. 주문번호나 상황을 알려주실 수 있을까요?"
    return "응, 계속 말해줘."

def _to_safe_turns(turns: Optional[List[Any]]) -> List[Dict[str, str]]:
    """dict/객체 섞여 들어와도 안전하게 role/text만 추출."""
    safe: List[Dict[str, str]] = []
    for t in (turns or []):
        if isinstance(t, dict):
            role = (t.get("role") or t.get("sender") or "user").lower()
            text = (t.get("text") or t.get("content") or "").strip()
        else:
            role = (getattr(t, "role", "user") or "user").lower()
            text = (getattr(t, "text", "") or getattr(t, "content", "") or "").strip()
        safe.append({"role": role, "text": text})
    return safe

@router.post("", response_model=ChatResponse)

def chat(req: ChatRequest):
    # 1) 예약 카테고리 중 LangGraph로 지원하는 시나리오는 graph router가 처리한다.
    reservation_graph_response = complete_reservation_graph_if_supported(req)
    if reservation_graph_response is not None:
        return reservation_graph_response

    # 2) 일반 시나리오 종료 감지
    if is_closing_utterance(getattr(req, "userMessage", "")):
        return ChatResponse(response=closing_line(req.category, req.userMessage))

    # 2) LLM 호출
    out = complete(req, timeout_s=OPENAI_TIMEOUT).strip()
    out = strip_labels(out)
    out = demote_question_if_repeated(out, _to_safe_turns(req.turns))
    out = strip_smalltalk_for_strict_categories(out, req.category)

    # 3) 예절 코멘트(필요 시)
    tip = maybe_get_etiquette_tip(
        category=req.category,
        turns=_to_safe_turns(req.turns),
        user_message=req.userMessage or "",
    )

    # 4) 응답(없으면 폴백) + tip 포함
    return ChatResponse(response=(out or _fallback_reply(req.category)), etiquetteTip=tip)

@router.post("/complete")
async def chat_complete(req: ChatRequest):
    sp, up = generate_prompts(req)
    return {"ok": True, "system": sp, "user": up}

# ⚠️ 기존에 실수로 추가했던  "/chat"  엔드포인트(= "/chat/chat") 는 삭제하세요.