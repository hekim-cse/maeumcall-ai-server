from __future__ import annotations

from typing import Dict

from services.flow.professor.assignment.extractor import extract_professor_assignment_info
from services.flow.professor.assignment.generation import generate_professor_assignment_ai_message
from services.flow.professor.assignment.policy import get_missing_professor_assignment_fields
from services.flow.professor.assignment.replies import get_professor_assignment_recommended_replies
from services.flow.professor.assignment.state import ProfessorAssignmentState


def extract_professor_assignment_info_node(state: ProfessorAssignmentState) -> Dict:
    """
    사용자 발화에서 교수님 과제 문의 정보를 추출한다.
    """
    user_message = state.get("user_message", "") or ""
    extracted = extract_professor_assignment_info(user_message)

    return {
        "intent": extracted.get("intent") or state.get("intent") or "assignment_inquiry",
        "professor_name": state.get("professor_name") or "교수님",
        "assignment_topic": extracted.get("assignment_topic") or state.get("assignment_topic"),
        "question": extracted.get("question") or state.get("question"),
        "user_name": extracted.get("user_name") or state.get("user_name"),
        "last_ai_message": state.get("last_ai_message"),
        "history": state.get("history") or [],
        "recommended_replies": state.get("recommended_replies") or [],
        "should_end_call": state.get("should_end_call", False),
    }


def decide_professor_assignment_state_node(state: ProfessorAssignmentState) -> Dict:
    """
    교수님 과제 문의 상태를 결정한다.
    """
    missing_fields = get_missing_professor_assignment_fields(state)

    if missing_fields:
        return {
            "missing_fields": missing_fields,
            "conversation_state": "collecting_assignment_info",
        }

    return {
        "missing_fields": [],
        "conversation_state": "answering_assignment_question",
        "user_action": "answer_ready",
    }


def generate_professor_assignment_response_node(state: ProfessorAssignmentState) -> Dict:
    """
    교수님 과제 문의 응답 생성 노드이다.

    LLM 응답을 우선 사용하고, 상태나 말투 기준에 맞지 않으면 fallback한다.
    """
    ai_message = generate_professor_assignment_ai_message(state)

    return {
        "ai_message": ai_message,
        "last_ai_message": ai_message,
    }


def attach_professor_assignment_recommended_replies_node(
    state: ProfessorAssignmentState,
) -> Dict:
    """
    현재 상태에 맞는 추천 답변을 붙인다.
    """
    conversation_state = state.get("conversation_state") or "collecting_assignment_info"

    return {
        "recommended_replies": get_professor_assignment_recommended_replies(
            conversation_state
        ),
    }
