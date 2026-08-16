from __future__ import annotations

from typing import Dict

from services.flow.professor.assignment.generation import (
    generate_professor_assignment_ai_message,
)
from services.flow.professor.assignment.llm_structured import (
    analyze_professor_assignment_user_message,
)
from services.flow.professor.assignment.policy import (
    get_missing_professor_assignment_fields,
)
from services.flow.professor.assignment.replies import (
    get_professor_assignment_recommended_replies,
)
from services.flow.professor.assignment.state import ProfessorAssignmentState


def extract_professor_assignment_info_node(state: ProfessorAssignmentState) -> Dict:
    """
    사용자 발화를 LLM structured output으로 분석하여 과제 문의 정보를 추출한다.
    """
    user_message = state.get("user_message", "") or ""
    conversation_state = state.get("conversation_state") or "greeting"

    analyzed = analyze_professor_assignment_user_message(
        conversation_state=conversation_state,
        user_message=user_message,
    )

    return {
        "intent": analyzed.get("intent") or state.get("intent") or "assignment_inquiry",
        "professor_name": state.get("professor_name") or "교수님",
        "course_name": analyzed.get("course_name") or state.get("course_name"),
        "course_name": analyzed.get("course_name") or state.get("course_name"),
        "assignment_topic": analyzed.get("assignment_topic")
        or state.get("assignment_topic"),
        "question": analyzed.get("question") or state.get("question"),
        "user_name": analyzed.get("user_name") or state.get("user_name"),
        "user_action": analyzed.get("user_action") or "unknown",
        "last_ai_message": state.get("last_ai_message"),
        "history": state.get("history") or [],
        "recommended_replies": state.get("recommended_replies") or [],
        "should_end_call": state.get("should_end_call", False),
    }


def decide_professor_assignment_state_node(state: ProfessorAssignmentState) -> Dict:
    """
    교수님 과제 문의 상태를 결정한다.
    """
    current_state = state.get("conversation_state") or "greeting"
    user_action = state.get("user_action") or "unknown"

    if current_state == "answering_assignment_question":
        if user_action == "ask_follow_up":
            return {
                "user_action": user_action,
                "assignment_topic": None,
                "question": None,
                "conversation_state": "collecting_assignment_info",
                "missing_fields": [],
                "should_end_call": False,
            }

        if user_action == "go_closing":
            return {
                "user_action": user_action,
                "conversation_state": "closing",
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
            "course_name": state.get("course_name"),
            "assignment_topic": state.get("assignment_topic"),
            "question": state.get("question"),
            "user_name": state.get("user_name"),
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

    검증된 상태를 교수님 과제 문의 응답 정책으로 표현한다.
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
