from __future__ import annotations

from typing import Dict

from services.flow.professor.assignment.action_parser import (
    parse_professor_assignment_action,
)
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
    user_message = state.get("user_message", "") or ""
    current_state = state.get("conversation_state") or "greeting"

    action_result = parse_professor_assignment_action(current_state, user_message)
    user_action = action_result.get("user_action")

    if current_state == "answering_assignment_question":
        if user_action == "go_closing":
            return {
                "user_action": user_action,
                "conversation_state": "closing",
                "should_end_call": False,
            }

        if user_action == "ask_follow_up":
            return {
                "user_action": user_action,
                "assignment_topic": None,
                "question": None,
                "missing_fields": ["assignment_topic", "question"],
                "conversation_state": "collecting_assignment_info",
                "should_end_call": False,
            }

        return {
            "user_action": user_action,
            "conversation_state": "answering_assignment_question",
        }

    if current_state == "closing":
        if user_action == "end_call":
            return {
                "user_action": user_action,
                "conversation_state": "END",
                "should_end_call": True,
            }

        return {
            "user_action": user_action,
            "conversation_state": "closing",
        }

    missing_fields = get_missing_professor_assignment_fields(state)

    if missing_fields:
        return {
            "user_action": user_action,
            "missing_fields": missing_fields,
            "conversation_state": "collecting_assignment_info",
        }

    return {
        "user_action": user_action,
        "missing_fields": [],
        "conversation_state": "answering_assignment_question",
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
