from __future__ import annotations

from typing import Optional

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.professor.appointment.response import (
    complete_professor_appointment_with_graph,
    is_professor_appointment_request,
)
from services.flow.professor.assignment.response import (
    complete_professor_assignment_with_graph,
    is_professor_assignment_request,
)


def complete_professor_graph_if_supported(req: ChatRequest) -> Optional[ChatResponse]:
    """
    교수님 카테고리 중 LangGraph로 지원하는 시나리오를 처리한다.

    현재 지원하는 graph:
    - 교수님 / 면담 예약
    - 교수님 / 과제 문의

    아직 지원하지 않는 교수님 시나리오:
    - 교수님 / 결석 사유 전달
    """
    if is_professor_appointment_request(req):
        return complete_professor_appointment_with_graph(req)

    if is_professor_assignment_request(req):
        return complete_professor_assignment_with_graph(req)

    return None
