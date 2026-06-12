from __future__ import annotations

from typing import Dict

from services.flow.professor.appointment.generation import (
    generate_professor_appointment_ai_message,
)
from services.flow.professor.appointment.llm_structured import (
    analyze_professor_appointment_user_message,
)
from services.flow.professor.appointment.policy import (
    get_missing_professor_appointment_fields,
)
from services.flow.professor.appointment.replies import (
    get_professor_appointment_recommended_replies,
)
from services.flow.professor.appointment.state import ProfessorAppointmentState


def extract_professor_appointment_info_node(state: ProfessorAppointmentState) -> Dict:
    """
    사용자 발화를 LLM structured output으로 분석하여 면담 예약 정보를 추출한다.
    """
    user_message = state.get("user_message", "") or ""
    conversation_state = state.get("conversation_state") or "greeting"

    analyzed = analyze_professor_appointment_user_message(
        conversation_state=conversation_state,
        user_message=user_message,
    )

    return {
        "intent": analyzed.get("intent") or state.get("intent") or "appointment_booking",
        "professor_name": state.get("professor_name") or "교수님",
        "appointment_purpose": analyzed.get("appointment_purpose")
        or state.get("appointment_purpose"),
        "date": analyzed.get("date") or state.get("date"),
        "time": analyzed.get("time") or state.get("time"),
        "user_name": analyzed.get("user_name") or state.get("user_name"),
        "user_action": analyzed.get("user_action") or "unknown",
        "last_ai_message": state.get("last_ai_message"),
        "history": state.get("history") or [],
        "recommended_replies": state.get("recommended_replies") or [],
        "should_end_call": state.get("should_end_call", False),
    }


def decide_professor_appointment_state_node(state: ProfessorAppointmentState) -> Dict:
    """
    교수님 면담 예약 상태를 결정한다.
    """
    current_state = state.get("conversation_state") or "greeting"
    user_action = state.get("user_action") or "unknown"

    if current_state == "confirming_info":
        if user_action == "confirm_info":
            return {
                "user_action": user_action,
                "conversation_state": "appointment_confirmed",
                "should_end_call": False,
            }

        if user_action == "change_purpose":
            return _reset_fields(
                {
                    "user_action": user_action,
                    "appointment_purpose": None,
                    "conversation_state": "collecting_appointment_info",
                    "should_end_call": False,
                }
            )

        if user_action == "change_date":
            return _reset_fields(
                {
                    "user_action": user_action,
                    "date": None,
                    "conversation_state": "collecting_appointment_info",
                    "should_end_call": False,
                }
            )

        if user_action == "change_time":
            return _reset_fields(
                {
                    "user_action": user_action,
                    "time": None,
                    "conversation_state": "collecting_appointment_info",
                    "should_end_call": False,
                }
            )

        if user_action == "change_user_name":
            return _reset_fields(
                {
                    "user_action": user_action,
                    "user_name": None,
                    "conversation_state": "collecting_appointment_info",
                    "should_end_call": False,
                }
            )

        return {
            "user_action": user_action,
            "conversation_state": "confirming_info",
        }

    if current_state == "appointment_confirmed":
        if user_action == "go_closing":
            return {
                "user_action": user_action,
                "conversation_state": "closing",
                "should_end_call": False,
            }

        return {
            "user_action": user_action,
            "conversation_state": "appointment_confirmed",
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

    missing_fields = get_missing_professor_appointment_fields(state)

    if missing_fields:
        return {
            "user_action": user_action,
            "missing_fields": missing_fields,
            "conversation_state": "collecting_appointment_info",
        }

    return {
        "user_action": user_action,
        "missing_fields": [],
        "conversation_state": "confirming_info",
    }


def generate_professor_appointment_response_node(state: ProfessorAppointmentState) -> Dict:
    """
    교수님 면담 예약 응답 생성 노드이다.

    LLM 응답을 우선 사용하고, 상태나 말투 기준에 맞지 않으면 fallback한다.
    """
    ai_message = generate_professor_appointment_ai_message(state)

    return {
        "ai_message": ai_message,
        "last_ai_message": ai_message,
    }


def attach_professor_appointment_recommended_replies_node(
    state: ProfessorAppointmentState,
) -> Dict:
    """
    현재 상태에 맞는 추천 답변을 붙인다.
    """
    conversation_state = state.get("conversation_state") or "collecting_appointment_info"

    return {
        "recommended_replies": get_professor_appointment_recommended_replies(
            conversation_state
        ),
    }


def _reset_fields(extra: Dict) -> Dict:
    """
    사용자가 일부 면담 정보를 변경하면 해당 필드를 비우고 다시 수집한다.
    """
    return {
        **extra,
        "missing_fields": [],
    }
