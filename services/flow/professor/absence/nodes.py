from __future__ import annotations

from typing import Dict

from services.flow.professor.absence.action_parser import (
    parse_professor_absence_action,
)
from services.flow.professor.absence.extractor import extract_professor_absence_info
from services.flow.professor.absence.generation import generate_professor_absence_ai_message
from services.flow.professor.absence.policy import get_missing_professor_absence_fields
from services.flow.professor.absence.replies import get_professor_absence_recommended_replies
from services.flow.professor.absence.state import ProfessorAbsenceState


def extract_professor_absence_info_node(state: ProfessorAbsenceState) -> Dict:
    """
    사용자 발화에서 교수님 결석 사유 전달 정보를 추출한다.
    """
    user_message = state.get("user_message", "") or ""
    extracted = extract_professor_absence_info(user_message)

    return {
        "intent": extracted.get("intent") or state.get("intent") or "absence_notice",
        "professor_name": state.get("professor_name") or "교수님",
        "class_name": extracted.get("class_name") or state.get("class_name"),
        "absence_date": extracted.get("absence_date") or state.get("absence_date"),
        "absence_reason": extracted.get("absence_reason") or state.get("absence_reason"),
        "user_name": extracted.get("user_name") or state.get("user_name"),
        "last_ai_message": state.get("last_ai_message"),
        "history": state.get("history") or [],
        "recommended_replies": state.get("recommended_replies") or [],
        "should_end_call": state.get("should_end_call", False),
    }


def decide_professor_absence_state_node(state: ProfessorAbsenceState) -> Dict:
    """
    교수님 결석 사유 전달 상태를 결정한다.
    """
    user_message = state.get("user_message", "") or ""
    current_state = state.get("conversation_state") or "greeting"

    action_result = parse_professor_absence_action(current_state, user_message)
    user_action = action_result.get("user_action")

    if current_state == "confirming_absence_info":
        if user_action == "confirm_absence_info":
            return {
                "user_action": user_action,
                "missing_fields": [],
                "conversation_state": "absence_noted",
                "should_end_call": False,
            }

        if user_action == "change_absence_date":
            return _reset_fields(
                {
                    "user_action": user_action,
                    "absence_date": None,
                    "conversation_state": "collecting_absence_info",
                    "should_end_call": False,
                }
            )

        if user_action == "change_absence_reason":
            return _reset_fields(
                {
                    "user_action": user_action,
                    "absence_reason": None,
                    "conversation_state": "collecting_absence_info",
                    "should_end_call": False,
                }
            )

        if user_action == "change_user_name":
            return _reset_fields(
                {
                    "user_action": user_action,
                    "user_name": None,
                    "conversation_state": "collecting_absence_info",
                    "should_end_call": False,
                }
            )

        return {
            "user_action": user_action,
            "conversation_state": "confirming_absence_info",
        }

    if current_state == "absence_noted":
        if user_action == "go_closing":
            return {
                "user_action": user_action,
                "conversation_state": "closing",
                "should_end_call": False,
            }

        return {
            "user_action": user_action,
            "conversation_state": "absence_noted",
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

    missing_fields = get_missing_professor_absence_fields(state)

    if missing_fields:
        return {
            "user_action": user_action,
            "missing_fields": missing_fields,
            "conversation_state": "collecting_absence_info",
        }

    return {
        "user_action": user_action,
        "missing_fields": [],
        "conversation_state": "confirming_absence_info",
    }


def generate_professor_absence_response_node(state: ProfessorAbsenceState) -> Dict:
    """
    교수님 결석 사유 전달 응답 생성 노드이다.

    LLM 응답을 우선 사용하고, 상태나 말투 기준에 맞지 않으면 fallback한다.
    """
    ai_message = generate_professor_absence_ai_message(state)

    return {
        "ai_message": ai_message,
        "last_ai_message": ai_message,
    }


def attach_professor_absence_recommended_replies_node(
    state: ProfessorAbsenceState,
) -> Dict:
    """
    현재 상태에 맞는 추천 답변을 붙인다.
    """
    conversation_state = state.get("conversation_state") or "collecting_absence_info"

    return {
        "recommended_replies": get_professor_absence_recommended_replies(
            conversation_state
        ),
    }


def _reset_fields(extra: Dict) -> Dict:
    """
    사용자가 일부 결석 정보를 변경하면 해당 필드를 비우고 다시 수집한다.
    """
    return {
        **extra,
        "missing_fields": [],
    }
