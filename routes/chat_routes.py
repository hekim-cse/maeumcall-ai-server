# routes/chat_routes.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException

from schemas.chat_models import ChatRequest, ChatResponse

from services.flow.registry import complete_graph_if_supported

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("", response_model=ChatResponse)

def chat(req: ChatRequest):
    graph_response = complete_graph_if_supported(req)
    if graph_response is not None:
        return graph_response

    raise HTTPException(
        status_code=422,
        detail={
            "code": "UNSUPPORTED_SCENARIO",
            "message": "등록되지 않은 카테고리와 제목 조합입니다.",
        },
    )
