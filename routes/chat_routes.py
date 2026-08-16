# routes/chat_routes.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException

from schemas.chat_models import ChatRequest, ChatResponse

from services.flow.reservation.router import complete_reservation_graph_if_supported
from services.flow.professor.router import complete_professor_graph_if_supported
from services.flow.scenario.response import complete_scenario_graph_if_supported

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("", response_model=ChatResponse)

def chat(req: ChatRequest):
    # 1) 예약 카테고리 중 LangGraph로 지원하는 시나리오는 graph router가 처리한다.
    reservation_graph_response = complete_reservation_graph_if_supported(req)
    if reservation_graph_response is not None:
        return reservation_graph_response

    professor_graph_response = complete_professor_graph_if_supported(req)
    if professor_graph_response is not None:
        return professor_graph_response

    scenario_graph_response = complete_scenario_graph_if_supported(req)
    if scenario_graph_response is not None:
        return scenario_graph_response

    raise HTTPException(
        status_code=422,
        detail={
            "code": "UNSUPPORTED_SCENARIO",
            "message": "등록되지 않은 카테고리와 제목 조합입니다.",
        },
    )
