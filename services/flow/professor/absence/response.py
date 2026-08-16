from __future__ import annotations

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.professor.absence.graph import professor_absence_graph
from services.flow.professor.absence.policy import compact_professor_absence_state
from services.flow.common.scenario_keys import scenario_matches


def is_professor_absence_request(req: ChatRequest) -> bool:
    """
    교수님 / 결석 사유 전달 시나리오인지 판단한다.
    """
    return scenario_matches(
        req.category,
        req.title,
        expected_category="교수님",
        expected_title="결석 사유 전달",
    )


def complete_professor_absence_with_graph(req: ChatRequest) -> ChatResponse:
    previous_state = getattr(req, "scenarioState", None) or {}
    history = getattr(req, "history", None) or previous_state.get("history") or []

    initial_state = {
        **previous_state,
        "user_message": getattr(req, "userMessage", "") or "",
        "professor_name": previous_state.get("professor_name") or "교수님",
        "conversation_state": (
            getattr(req, "conversationState", None)
            or previous_state.get("conversation_state")
            or "greeting"
        ),
        "history": history,
        "recommended_replies": [],
        "should_end_call": False,
    }

    result = professor_absence_graph.invoke(initial_state)

    ai_message = result["ai_message"]
    conversation_state = result["conversation_state"]
    recommended_replies = result["recommended_replies"]
    should_end_call = result["should_end_call"]

    return ChatResponse(
        response=ai_message,
        etiquetteTip=None,
        recommendedReplies=recommended_replies,
        conversationState=conversation_state,
        shouldEndCall=should_end_call,
        scenarioState=compact_professor_absence_state(result),
    )
